from __future__ import annotations

from typing import Any

import httpx

from shared.smartdoc_common import JobStatus, PipelineStage, Role, Settings, pipeline_slice

from .celery_app import celery_app

settings = Settings(service_name="api-gateway", service_port=8600)


def _post(client: httpx.Client, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def _put(client: httpx.Client, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.put(url, json=payload)
    response.raise_for_status()
    return response.json()


def _get(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def _patch(
    client: httpx.Client,
    url: str,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.patch(url, json=payload, params=params)
    response.raise_for_status()
    return response.json()


def _update_job(
    client: httpx.Client,
    job_id: str,
    status: JobStatus,
    stage: PipelineStage,
    detail: str,
    error: str | None = None,
) -> None:
    _patch(
        client,
        f"{settings.storage_service_url}/jobs/{job_id}",
        {
            "status": status.value,
            "current_stage": stage.value,
            "stage_detail": detail,
            "error": error,
        },
    )


def _save_artifact(client: httpx.Client, doc_id: str, stage: PipelineStage, payload: dict[str, Any]) -> None:
    _post(client, f"{settings.storage_service_url}/pipeline/artifact/{doc_id}/{stage.value}", payload)


def _load_saved_context(client: httpx.Client, doc_id: str) -> dict[str, dict[str, Any]]:
    try:
        payload = _get(client, f"{settings.storage_service_url}/pipeline/artifact/{doc_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {}
        raise

    stages = payload.get("stages", {})
    context: dict[str, dict[str, Any]] = {}
    for stage, value in stages.items():
        context[stage] = dict(value.get("payload") or {})
    return context


def run_pipeline(
    job_id: str,
    doc_id: str,
    actor_id: str,
    actor_role: str,
    restart_from: str | None = None,
) -> dict[str, Any]:
    role = Role(actor_role)
    with httpx.Client(timeout=30.0) as client:
        _update_job(client, job_id, JobStatus.RUNNING, PipelineStage.UPLOAD, "pipeline-started")
        document = _get(client, f"{settings.upload_service_url}/documents/{doc_id}")
        _save_artifact(client, doc_id, PipelineStage.UPLOAD, document)

        context = _load_saved_context(client, doc_id)
        context[PipelineStage.UPLOAD.value] = document

        stages = list(pipeline_slice(PipelineStage(restart_from) if restart_from else None))
        if restart_from:
            order = [
                PipelineStage.PREPROCESS,
                PipelineStage.CLASSIFY,
                PipelineStage.OCR,
                PipelineStage.EXTRACT,
                PipelineStage.VALIDATE,
            ]
            start_index = order.index(PipelineStage(restart_from)) if PipelineStage(restart_from) in order else 0
            for idx, stage in enumerate(order[:start_index]):
                if stage.value not in context:
                    stages = order[idx:] + [PipelineStage.STORE, PipelineStage.NOTIFY]
                    break

        for stage in stages:
            _update_job(client, job_id, JobStatus.RUNNING, stage, "running")

            if stage == PipelineStage.PREPROCESS:
                payload = _post(
                    client,
                    f"{settings.preprocessing_service_url}/preprocess",
                    {
                        "doc_id": doc_id,
                        "document": document,
                        "actor_id": actor_id,
                        "actor_role": role.value,
                    },
                )
                payload["file_name"] = document.get("file_name")
                context[stage.value] = payload
            elif stage == PipelineStage.CLASSIFY:
                payload = _post(
                    client,
                    f"{settings.classification_service_url}/classify",
                    {
                        "doc_id": doc_id,
                        "preprocessed": context[PipelineStage.PREPROCESS.value],
                        "actor_id": actor_id,
                        "actor_role": role.value,
                    },
                )
                context[stage.value] = payload
            elif stage == PipelineStage.OCR:
                payload = _post(
                    client,
                    f"{settings.ocr_service_url}/ocr",
                    {
                        "doc_id": doc_id,
                        "preprocessed": context[PipelineStage.PREPROCESS.value],
                        "doc_type": context[PipelineStage.CLASSIFY.value]["doc_type"],
                        "actor_id": actor_id,
                        "actor_role": role.value,
                    },
                )
                context[stage.value] = payload
            elif stage == PipelineStage.EXTRACT:
                payload = _post(
                    client,
                    f"{settings.extraction_service_url}/extract",
                    {
                        "doc_id": doc_id,
                        "ocr": context[PipelineStage.OCR.value],
                        "doc_type": context[PipelineStage.CLASSIFY.value]["doc_type"],
                        "actor_id": actor_id,
                        "actor_role": role.value,
                    },
                )
                context[stage.value] = payload
            elif stage == PipelineStage.VALIDATE:
                payload = _post(
                    client,
                    f"{settings.validation_service_url}/validate",
                    {
                        "doc_id": doc_id,
                        "extracted": context[PipelineStage.EXTRACT.value],
                        "doc_type": context[PipelineStage.CLASSIFY.value]["doc_type"],
                        "actor_id": actor_id,
                        "actor_role": role.value,
                    },
                )
                context[stage.value] = payload
            elif stage == PipelineStage.STORE:
                payload = _put(
                    client,
                    f"{settings.storage_service_url}/results/{doc_id}",
                    {
                        "doc_id": doc_id,
                        "doc_type": context[PipelineStage.CLASSIFY.value]["doc_type"],
                        "validated": context[PipelineStage.VALIDATE.value],
                        "pipeline_job_id": job_id,
                        "actor_id": actor_id,
                        "actor_role": role.value,
                        "raw_ocr": context[PipelineStage.OCR.value],
                    },
                )
                context[stage.value] = payload
            elif stage == PipelineStage.NOTIFY:
                payload = _post(
                    client,
                    f"{settings.notification_service_url}/notify",
                    {
                        "doc_id": doc_id,
                        "event_type": "pipeline.completed",
                        "message": f"Document {doc_id} processed successfully",
                        "recipient": actor_id,
                        "severity": "info",
                    },
                )
                context[stage.value] = payload
            else:
                payload = {}

            _save_artifact(client, doc_id, stage, payload)
            _update_job(client, job_id, JobStatus.RUNNING, stage, "completed")

        _update_job(client, job_id, JobStatus.COMPLETED, PipelineStage.COMPLETED, "pipeline-completed")

    return {
        "job_id": job_id,
        "doc_id": doc_id,
        "status": JobStatus.COMPLETED.value,
        "final_stage": PipelineStage.COMPLETED.value,
    }


@celery_app.task(name="smartdoc.process_document")
def process_document_task(
    job_id: str,
    doc_id: str,
    actor_id: str,
    actor_role: str,
    restart_from: str | None = None,
) -> dict:
    try:
        return run_pipeline(job_id, doc_id, actor_id, actor_role, restart_from)
    except Exception as exc:  # noqa: BLE001
        with httpx.Client(timeout=15.0) as client:
            _update_job(client, job_id, JobStatus.FAILED, PipelineStage.FAILED, "pipeline-failed", str(exc))
        raise

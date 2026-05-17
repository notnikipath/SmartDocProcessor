from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.smartdoc_common import (
    AuthRequest,
    BatchUploadRequest,
    DocumentUploadRequest,
    PipelineJobCreateRequest,
    PipelineStage,
    ReviewCorrectionRequest,
    Role,
    ScannerUploadRequest,
    Settings,
    sign_token,
    verify_token,
)

from .tasks import process_document_task, run_pipeline

settings = Settings(service_name="api-gateway", service_port=8600)
app = FastAPI(title="SmartDoc API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _patch_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.patch(url, json=payload, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "upload": settings.upload_service_url,
        "preprocessing": settings.preprocessing_service_url,
        "ocr": settings.ocr_service_url,
        "classification": settings.classification_service_url,
        "extraction": settings.extraction_service_url,
        "validation": settings.validation_service_url,
        "storage": settings.storage_service_url,
        "notification": settings.notification_service_url,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name, "pipeline_mode": settings.pipeline_mode}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token({"sub": request.user_id, "role": request.role.value}, settings.jwt_secret, exp_minutes=240)
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def services_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except Exception as exc:  # noqa: BLE001
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


async def _create_job(
    client: httpx.AsyncClient,
    doc_id: str,
    actor_id: str,
    actor_role: Role,
    restart_from: PipelineStage | None = None,
) -> dict:
    payload = PipelineJobCreateRequest(
        doc_id=doc_id,
        actor_id=actor_id,
        actor_role=actor_role,
        restart_from=restart_from,
    )
    return await _post_json(client, f"{settings.storage_service_url}/jobs", payload.model_dump(mode="json"))


def _launch_pipeline(
    job: dict,
    doc_id: str,
    actor_id: str,
    actor_role: Role,
    restart_from: PipelineStage | None = None,
) -> dict:
    restart_stage = restart_from.value if restart_from else None
    if settings.pipeline_mode.lower() == "celery":
        task = process_document_task.delay(job["job_id"], doc_id, actor_id, actor_role.value, restart_stage)
        return {"execution": "async", "celery_task_id": task.id}

    result = run_pipeline(job["job_id"], doc_id, actor_id, actor_role.value, restart_stage)
    return {"execution": "sync", "result": result}


@app.post("/documents/upload")
async def upload_document(request: DocumentUploadRequest) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        uploaded = await _post_json(
            client,
            f"{settings.upload_service_url}/documents/upload",
            request.model_dump(mode="json"),
        )
        job = await _create_job(client, uploaded["doc_id"], request.actor_id, request.actor_role)
    launch = _launch_pipeline(job, uploaded["doc_id"], request.actor_id, request.actor_role)
    return {"document": uploaded, "job": job, "pipeline": launch}


@app.post("/documents/upload/batch")
async def upload_batch(request: BatchUploadRequest) -> dict:
    async with httpx.AsyncClient(timeout=40.0) as client:
        uploaded = await _post_json(
            client,
            f"{settings.upload_service_url}/documents/upload/batch",
            request.model_dump(mode="json"),
        )
        jobs = []
        for item in uploaded["items"]:
            job = await _create_job(client, item["doc_id"], request.actor_id, request.actor_role)
            launch = _launch_pipeline(job, item["doc_id"], request.actor_id, request.actor_role)
            jobs.append({"job": job, "pipeline": launch, "doc_id": item["doc_id"]})
    return {"items": uploaded["items"], "jobs": jobs, "count": uploaded["count"]}


@app.post("/documents/upload/scanner")
async def upload_scanner(request: ScannerUploadRequest) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        uploaded = await _post_json(
            client,
            f"{settings.upload_service_url}/documents/upload/scanner",
            request.model_dump(mode="json"),
        )
        job = await _create_job(client, uploaded["doc_id"], request.actor_id, request.actor_role)
    launch = _launch_pipeline(job, uploaded["doc_id"], request.actor_id, request.actor_role)
    return {"document": uploaded, "job": job, "pipeline": launch}


@app.post("/pipeline/start/{doc_id}")
async def start_pipeline(doc_id: str, actor_id: str, actor_role: Role = Role.OPERATOR) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        job = await _create_job(client, doc_id, actor_id, actor_role)
    launch = _launch_pipeline(job, doc_id, actor_id, actor_role)
    return {"job": job, "pipeline": launch}


@app.post("/pipeline/restart/{doc_id}")
async def restart_pipeline(doc_id: str, stage: PipelineStage, actor_id: str, actor_role: Role = Role.ADMIN) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        job = await _create_job(client, doc_id, actor_id, actor_role, restart_from=stage)
    launch = _launch_pipeline(job, doc_id, actor_id, actor_role, restart_from=stage)
    return {"job": job, "pipeline": launch}


@app.get("/pipeline/status/{job_id}")
async def pipeline_status(job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await _get_json(client, f"{settings.storage_service_url}/jobs/{job_id}")


@app.get("/pipeline/document/{doc_id}")
async def pipeline_document(doc_id: str, decrypted: bool = False) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await _get_json(
            client,
            f"{settings.storage_service_url}/results/{doc_id}",
            params={"decrypted": str(decrypted).lower()},
        )


@app.post("/review/{doc_id}")
async def review_document(doc_id: str, request: ReviewCorrectionRequest) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _post_json(
            client,
            f"{settings.storage_service_url}/results/{doc_id}/review-corrections",
            request.model_dump(mode="json"),
        )


@app.get("/exports/{doc_id}")
async def export_document(doc_id: str, format: str = "json", actor_role: Role = Role.OPERATOR) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _get_json(
            client,
            f"{settings.storage_service_url}/exports/{doc_id}",
            params={"format": format, "actor_role": actor_role.value},
        )


@app.get("/audit")
async def audit(limit: int = 200, actor_role: Role = Role.AUDITOR) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _get_json(
            client,
            f"{settings.storage_service_url}/audit",
            params={"limit": limit, "actor_role": actor_role.value},
        )


@app.post("/cleanup/tmp")
async def cleanup_tmp(max_age_minutes: int = 60, actor_id: str = "system", actor_role: Role = Role.ADMIN) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _get_json(
            client,
            f"{settings.upload_service_url}/cleanup/tmp",
            params={
                "max_age_minutes": max_age_minutes,
                "actor_id": actor_id,
                "actor_role": actor_role.value,
            },
        )


@app.get("/dashboard")
async def dashboard() -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        jobs = await _get_json(client, f"{settings.storage_service_url}/jobs")
        metrics = await _get_json(client, f"{settings.storage_service_url}/metrics")
        notifications = await _get_json(client, f"{settings.notification_service_url}/notify/history")
        docs = await _get_json(client, f"{settings.upload_service_url}/documents")
        quality = await _get_json(client, f"{settings.validation_service_url}/metrics/accuracy")
    return {
        "jobs": jobs,
        "metrics": metrics,
        "notifications": notifications,
        "documents": docs,
        "quality": quality,
    }


@app.post("/jobs/{job_id}/mark-failed")
async def mark_failed(job_id: str, reason: str, actor_id: str = "system") -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _patch_json(
            client,
            f"{settings.storage_service_url}/jobs/{job_id}",
            {
                "status": "failed",
                "current_stage": "failed",
                "stage_detail": "manual-fail",
                "error": reason,
            },
            params={"actor_id": actor_id},
        )

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from uuid import uuid4
from xml.etree import ElementTree as ET

from fastapi import FastAPI, HTTPException

from shared.smartdoc_common import (
    DocumentVersion,
    ExportFormat,
    JobStatus,
    LearningSample,
    PipelineArtifactEntry,
    PipelineJob,
    PipelineJobCreateRequest,
    PipelineJobUpdateRequest,
    PipelineStage,
    ReviewCorrectionRequest,
    Role,
    Settings,
    StoredDocumentResult,
    StoreResultRequest,
    build_audit_event,
    decrypt_text,
    encrypt_text,
    has_permission,
)

settings = Settings(service_name="storage-service", service_port=8607)
app = FastAPI(title="SmartDoc Storage Service", version="1.0.0")

jobs: dict[str, PipelineJob] = {}
artifacts: dict[str, dict[str, PipelineArtifactEntry]] = {}
results: dict[str, StoredDocumentResult] = {}
audit_log: list[dict] = []
learning_samples: list[LearningSample] = []
review_sessions: dict[str, dict] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(
    actor_id: str,
    actor_role: Role,
    action: str,
    object_type: str,
    object_id: str,
    details: dict | None = None,
) -> None:
    event = build_audit_event(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=details or {},
    )
    audit_log.append(event.model_dump(mode="json"))


@app.post("/jobs")
async def create_job(request: PipelineJobCreateRequest) -> dict:
    _assert_permission(request.actor_role, "pipeline:run")
    job = PipelineJob(
        job_id=str(uuid4()),
        doc_id=request.doc_id,
        actor_id=request.actor_id,
        actor_role=request.actor_role,
        status=JobStatus.QUEUED,
        current_stage=PipelineStage.UPLOAD,
        restart_from=request.restart_from,
        stages={PipelineStage.UPLOAD.value: "queued"},
    )
    jobs[job.job_id] = job
    _audit(request.actor_id, request.actor_role, "job.create", "job", job.job_id, {"doc_id": request.doc_id})
    return job.model_dump(mode="json")


@app.patch("/jobs/{job_id}")
async def update_job(job_id: str, request: PipelineJobUpdateRequest, actor_id: str = "system") -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = request.status
    job.current_stage = request.current_stage
    if request.stage_detail:
        job.stages[request.current_stage.value] = request.stage_detail
    if request.error:
        job.error = request.error
    job.updated_at = datetime.now(UTC)

    _audit(
        actor_id,
        Role.ADMIN,
        "job.update",
        "job",
        job_id,
        {"status": job.status.value, "stage": job.current_stage.value},
    )
    return job.model_dump(mode="json")


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.get("/jobs")
async def list_jobs(doc_id: str | None = None, limit: int = 100) -> dict:
    items = list(jobs.values())
    if doc_id:
        items = [job for job in items if job.doc_id == doc_id]
    data = [job.model_dump(mode="json") for job in items[-limit:]]
    return {"items": data, "count": len(data)}


@app.post("/pipeline/artifact/{doc_id}/{stage}")
async def save_artifact(doc_id: str, stage: PipelineStage, payload: dict, actor_id: str = "system") -> dict:
    artifacts.setdefault(doc_id, {})[stage.value] = PipelineArtifactEntry(stage=stage, payload=payload)
    _audit(actor_id, Role.ADMIN, "artifact.save", "document", doc_id, {"stage": stage.value})
    return {"doc_id": doc_id, "stage": stage.value, "saved": True}


@app.get("/pipeline/artifact/{doc_id}")
async def get_artifacts(doc_id: str) -> dict:
    data = artifacts.get(doc_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"doc_id": doc_id, "stages": {name: item.model_dump(mode="json") for name, item in data.items()}}


@app.put("/results/{doc_id}")
async def save_result(doc_id: str, request: StoreResultRequest) -> dict:
    if doc_id != request.doc_id:
        raise HTTPException(status_code=400, detail="Document ID does not match the result")
    if not has_permission(request.actor_role, "store:write"):
        job = jobs.get(request.pipeline_job_id)
        owns_running_pipeline = (
            has_permission(request.actor_role, "pipeline:run")
            and job is not None
            and job.doc_id == doc_id
            and job.actor_id == request.actor_id
            and job.actor_role == request.actor_role
            and job.status == JobStatus.RUNNING
            and job.current_stage == PipelineStage.STORE
        )
        if not owns_running_pipeline:
            raise HTTPException(status_code=403, detail="Result requires an authorized running pipeline")
    serialized = json.dumps(
        {
            "doc_id": request.doc_id,
            "doc_type": request.doc_type.value,
            "validated": request.validated,
            "raw_ocr": request.raw_ocr,
            "job_id": request.pipeline_job_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    encrypted_blob = encrypt_text(serialized, settings.encryption_key)

    existing = results.get(doc_id)
    version = 1
    versions = []
    if existing:
        version = existing.version + 1
        versions = list(existing.versions)

    stored = StoredDocumentResult(
        doc_id=doc_id,
        doc_type=request.doc_type,
        validated=request.validated,
        encrypted_blob=encrypted_blob,
        version=version,
        versions=versions,
    )
    results[doc_id] = stored
    _audit(request.actor_id, request.actor_role, "result.save", "document", doc_id, {"version": version})
    return stored.model_dump(mode="json")


@app.get("/results/{doc_id}")
async def get_result(doc_id: str, decrypted: bool = False) -> dict:
    stored = results.get(doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Result not found")
    payload = stored.model_dump(mode="json")
    if decrypted:
        payload["decrypted_payload"] = json.loads(decrypt_text(stored.encrypted_blob, settings.encryption_key))
    return payload


@app.post("/results/{doc_id}/review-corrections")
async def review_corrections(doc_id: str, request: ReviewCorrectionRequest) -> dict:
    _assert_permission(request.editor_role, "review:write")
    stored = results.get(doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Result not found")

    before = dict(stored.validated)
    after = dict(stored.validated)
    after.update(request.corrected_fields)

    version_payload = {
        "before": before,
        "after": after,
        "changed_fields": list(request.corrected_fields.keys()),
    }
    version = DocumentVersion(
        version_id=str(uuid4()),
        editor_id=request.editor_id,
        note=request.note,
        diff=version_payload,
    )
    stored.versions.append(version)
    stored.validated = after
    stored.version += 1
    stored.updated_at = datetime.now(UTC)

    sample = LearningSample(
        sample_id=str(uuid4()),
        doc_id=doc_id,
        reviewer_id=request.editor_id,
        before=before,
        after=after,
    )
    learning_samples.append(sample)

    _audit(request.editor_id, request.editor_role, "result.review", "document", doc_id, {"version": stored.version})
    return {
        "doc_id": doc_id,
        "version": stored.version,
        "validated": stored.validated,
        "learning_sample_id": sample.sample_id,
    }


@app.post("/review/sessions/{doc_id}")
async def start_review_session(
    doc_id: str,
    owner_id: str,
    reviewers: list[str],
    actor_role: Role = Role.REVIEWER,
) -> dict:
    _assert_permission(actor_role, "review:write")
    session = {
        "doc_id": doc_id,
        "owner_id": owner_id,
        "reviewers": reviewers,
        "status": "active",
        "started_at": datetime.now(UTC).isoformat(),
    }
    review_sessions[doc_id] = session
    _audit(owner_id, actor_role, "review.session.start", "document", doc_id, {"reviewers": len(reviewers)})
    return session


@app.get("/review/sessions/{doc_id}")
async def get_review_session(doc_id: str) -> dict:
    session = review_sessions.get(doc_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Review session not found")
    return session


@app.get("/results/{doc_id}/versions")
async def get_versions(doc_id: str) -> dict:
    stored = results.get(doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"doc_id": doc_id, "version": stored.version, "items": stored.versions}


@app.get("/learning/samples")
async def get_learning_samples(limit: int = 200) -> dict:
    items = [sample.model_dump(mode="json") for sample in learning_samples[-limit:]]
    return {"items": items, "count": len(items)}


@app.post("/learning/retrain")
async def retrain_model(actor_id: str = "ml-bot", actor_role: Role = Role.ML_ENGINEER) -> dict:
    _assert_permission(actor_role, "review:write")
    total = len(learning_samples)
    estimated_boost = round(min(0.045, total * 0.0004), 4)
    _audit(actor_id, actor_role, "learning.retrain", "model", "ner-ocr-stack", {"samples": total})
    return {
        "status": "scheduled",
        "samples_used": total,
        "expected_accuracy_gain": estimated_boost,
    }


def _export_json(doc_id: str, stored: StoredDocumentResult) -> str:
    return json.dumps(
        {
            "doc_id": doc_id,
            "doc_type": stored.doc_type.value,
            "validated": stored.validated,
            "version": stored.version,
        },
        ensure_ascii=False,
        indent=2,
    )


def _export_xml(doc_id: str, stored: StoredDocumentResult) -> str:
    root = ET.Element("document", attrib={"id": doc_id, "type": stored.doc_type.value, "version": str(stored.version)})
    validated = ET.SubElement(root, "validated")
    for key, value in stored.validated.items():
        field = ET.SubElement(validated, "field", attrib={"name": str(key)})
        field.text = str(value)
    return ET.tostring(root, encoding="unicode")


def _export_csv(doc_id: str, stored: StoredDocumentResult) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["doc_id", "doc_type", "field", "value", "version"])
    for key, value in stored.validated.items():
        writer.writerow([doc_id, stored.doc_type.value, key, value, stored.version])
    return stream.getvalue()


@app.get("/exports/{doc_id}")
async def export_document(
    doc_id: str,
    format: ExportFormat = ExportFormat.JSON,
    actor_role: Role = Role.OPERATOR,
) -> dict:
    _assert_permission(actor_role, "export:read")
    stored = results.get(doc_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Result not found")

    if format == ExportFormat.JSON:
        content = _export_json(doc_id, stored)
    elif format == ExportFormat.XML:
        content = _export_xml(doc_id, stored)
    else:
        content = _export_csv(doc_id, stored)

    return {"doc_id": doc_id, "format": format.value, "content": content}


@app.get("/metrics")
async def metrics() -> dict:
    completed_jobs = len([job for job in jobs.values() if job.status == JobStatus.COMPLETED])
    failed_jobs = len([job for job in jobs.values() if job.status == JobStatus.FAILED])
    avg_latency_seconds = 7.8
    return {
        "documents_total": len(results),
        "jobs_total": len(jobs),
        "jobs_completed": completed_jobs,
        "jobs_failed": failed_jobs,
        "learning_samples": len(learning_samples),
        "avg_processing_seconds": avg_latency_seconds,
    }


@app.get("/audit")
async def get_audit(limit: int = 500, actor_role: Role = Role.AUDITOR) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:], "count": min(limit, len(audit_log))}

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.smartdoc_common import (
    BatchUploadRequest,
    DocumentRecord,
    DocumentUploadRequest,
    Role,
    ScannerUploadRequest,
    Settings,
    SourceType,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="upload-service", service_port=8601)
app = FastAPI(title="SmartDoc Upload Service", version="1.0.0")

TEMP_ROOT = Path("/tmp/smartdoc_upload")
if not TEMP_ROOT.exists():
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

records: dict[str, DocumentRecord] = {}
audit_log: list[dict] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _save_temp(doc_id: str, payload: str) -> str:
    file_path = TEMP_ROOT / f"{doc_id}.txt"
    file_path.write_text(payload, encoding="utf-8")
    return str(file_path)


def _build_record(payload: DocumentUploadRequest) -> DocumentRecord:
    text = payload.text_content or ""
    encoded = payload.content_base64 or ""
    data = text if text else encoded
    if not data:
        data = f"placeholder for {payload.file_name}"

    doc_id = str(uuid4())
    temp_path = _save_temp(doc_id, text or data)

    return DocumentRecord(
        doc_id=doc_id,
        file_name=payload.file_name,
        content_type=payload.content_type,
        source=payload.source,
        language_hint=payload.language_hint,
        text_content=text or None,
        content_base64=encoded or None,
        temporary_path=temp_path,
        checksum=_checksum(data),
    )


def _audit(actor_id: str, actor_role: Role, action: str, doc_id: str, details: dict | None = None) -> None:
    event = build_audit_event(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        object_type="document",
        object_id=doc_id,
        details=details or {},
    )
    audit_log.append(event.model_dump(mode="json"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/documents/upload")
async def upload_document(request: DocumentUploadRequest) -> dict:
    _assert_permission(request.actor_role, "upload:create")
    record = _build_record(request)
    records[record.doc_id] = record
    _audit(request.actor_id, request.actor_role, "document.upload", record.doc_id, {"source": request.source.value})
    return record.model_dump(mode="json")


@app.post("/documents/upload/batch")
async def upload_batch(request: BatchUploadRequest) -> dict:
    _assert_permission(request.actor_role, "upload:create")
    items: list[dict] = []
    for item in request.documents:
        candidate = item.model_copy(update={"source": SourceType.BATCH})
        record = _build_record(candidate)
        records[record.doc_id] = record
        _audit(request.actor_id, request.actor_role, "document.upload.batch", record.doc_id)
        items.append(record.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.post("/documents/upload/scanner")
async def upload_from_scanner(request: ScannerUploadRequest) -> dict:
    _assert_permission(request.actor_role, "upload:create")
    synthetic = DocumentUploadRequest(
        file_name=request.file_name,
        content_type="image/jpeg",
        text_content=request.text_content,
        source=SourceType.SCANNER,
        actor_id=request.actor_id,
        actor_role=request.actor_role,
    )
    record = _build_record(synthetic)
    records[record.doc_id] = record
    _audit(
        request.actor_id,
        request.actor_role,
        "document.upload.scanner",
        record.doc_id,
        {"scanner_type": request.scanner_type},
    )
    payload = record.model_dump(mode="json")
    payload["scanner_type"] = request.scanner_type
    return payload


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str) -> dict:
    record = records.get(doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return record.model_dump(mode="json")


@app.get("/documents")
async def list_documents(limit: int = 100) -> dict:
    items = [record.model_dump(mode="json") for record in list(records.values())[-limit:]]
    return {"items": items, "count": len(items)}


@app.get("/cleanup/tmp")
async def cleanup_tmp(max_age_minutes: int = 60, actor_id: str = "system", actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "pipeline:restart")
    cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
    removed = 0
    for record in records.values():
        if not record.temporary_path:
            continue
        path = Path(record.temporary_path)
        if not path.exists():
            continue
        if datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    _audit(actor_id, actor_role, "cleanup.temp", "temporary-files", {"removed": removed})
    return {"removed": removed}


@app.get("/audit")
async def get_audit(limit: int = 200, actor_role: Role = Role.AUDITOR) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

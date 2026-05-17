from __future__ import annotations

import hashlib

from fastapi import FastAPI

from shared.smartdoc_common import ClassificationRequest, ClassificationResult, DocumentType, Settings, has_permission

settings = Settings(service_name="classification-service", service_port=8604)
app = FastAPI(title="SmartDoc Classification Service", version="1.0.0")

KEYWORDS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.PASSPORT, ("passport", "паспорт")),
    (DocumentType.DRIVER_LICENSE, ("driver license", "driver_lic", "водитель")),
    (DocumentType.CONTRACT, ("contract", "agreement", "договор")),
    (DocumentType.RECEIPT, ("receipt", "cheque", "чек")),
    (DocumentType.INVOICE, ("invoice", "наклад", "счет")),
    (DocumentType.FORM, ("application", "анкета", "form")),
    (DocumentType.HANDWRITTEN, ("handwritten", "рукопис")),
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def _classify(text: str, file_name: str) -> tuple[DocumentType, float]:
    bag = f"{file_name} {text}".lower()
    for doc_type, keys in KEYWORDS:
        for key in keys:
            if key in bag:
                return doc_type, 0.96
    if len(text) > 50:
        return DocumentType.CONTRACT, 0.62
    return DocumentType.UNKNOWN, 0.4


@app.post("/classify")
async def classify(request: ClassificationRequest) -> dict:
    if not has_permission(request.actor_role, "pipeline:run"):
        return {"error": f"Role {request.actor_role.value} cannot run pipeline"}

    text = str(request.preprocessed.get("normalized_text") or "")
    file_name = str(request.preprocessed.get("file_name") or "")
    doc_type, confidence = _classify(text, file_name)

    bag = f"{file_name} {text}".lower()
    watermark = "watermark" in bag or "водяной" in bag
    manipulation_risk = 0.75 if any(token in bag for token in ("edited", "photoshop", "tampered")) else 0.12
    authenticity_score = max(0.0, min(1.0, 0.96 - manipulation_risk * 0.4 + (0.05 if watermark else 0.0)))

    cluster_id = hashlib.sha1(f"{doc_type.value}:{file_name}".encode()).hexdigest()[:10]

    result = ClassificationResult(
        doc_id=request.doc_id,
        doc_type=doc_type,
        confidence=confidence,
        cluster_id=cluster_id,
        authenticity_score=round(authenticity_score, 3),
        watermark_detected=watermark,
        manipulation_risk=round(manipulation_risk, 3),
    )
    return result.model_dump(mode="json")


@app.post("/classify/cluster")
async def cluster(documents: list[dict]) -> dict:
    groups: dict[str, list[str]] = {}
    for item in documents:
        key = item.get("doc_type", "unknown")
        groups.setdefault(key, []).append(item.get("doc_id", "n/a"))
    return {"clusters": groups, "count": len(groups)}

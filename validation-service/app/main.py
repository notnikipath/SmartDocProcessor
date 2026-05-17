from __future__ import annotations

from fastapi import FastAPI

from shared.smartdoc_common import (
    DocumentType,
    Role,
    Settings,
    ValidationIssue,
    ValidationRequest,
    ValidationResult,
    has_permission,
)

settings = Settings(service_name="validation-service", service_port=8606)
app = FastAPI(title="SmartDoc Validation Service", version="1.0.0")

TEMPLATES: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.PASSPORT: ("person", "document_number", "date"),
    DocumentType.DRIVER_LICENSE: ("person", "document_number", "date"),
    DocumentType.CONTRACT: ("person", "date"),
    DocumentType.RECEIPT: ("amount", "date"),
    DocumentType.INVOICE: ("amount", "date", "document_number"),
    DocumentType.FORM: ("person", "date"),
    DocumentType.HANDWRITTEN: ("date",),
    DocumentType.UNKNOWN: tuple(),
}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/templates")
async def templates() -> dict:
    return {"templates": {doc_type.value: fields for doc_type, fields in TEMPLATES.items()}}


def _parse_amount(raw: str) -> float | None:
    cleaned = raw.replace("RUB", "").replace("руб", "").replace(" ", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except Exception:
        return None


@app.post("/validate")
async def validate(request: ValidationRequest) -> dict:
    if not has_permission(request.actor_role, "pipeline:run"):
        return {"error": f"Role {request.actor_role.value} cannot run pipeline"}

    extracted = dict(request.extracted)
    fields = dict(extracted.get("key_fields") or {})
    required = TEMPLATES.get(request.doc_type, tuple())
    issues: list[ValidationIssue] = []

    for field in required:
        if not fields.get(field):
            issues.append(ValidationIssue(field=field, severity="high", message="Missing required field"))

    normalized = dict(fields)
    if "amount" in fields:
        parsed_amount = _parse_amount(str(fields["amount"]))
        if parsed_amount is None:
            issues.append(ValidationIssue(field="amount", severity="medium", message="Amount parsing failed"))
        elif parsed_amount < 0:
            issues.append(ValidationIssue(field="amount", severity="high", message="Amount must be positive"))
        else:
            normalized["amount"] = parsed_amount

    confidence = max(0.0, min(1.0, 0.96 - len(issues) * 0.18))
    is_valid = len([item for item in issues if item.severity == "high"]) == 0
    status = "valid" if is_valid and confidence >= 0.8 else "needs_review"

    result = ValidationResult(
        doc_id=request.doc_id,
        is_valid=is_valid,
        status=status,
        confidence=round(confidence, 3),
        issues=issues,
        normalized=normalized,
    )
    return result.model_dump(mode="json")


@app.get("/metrics/accuracy")
async def mock_accuracy() -> dict:
    return {
        "ocr_accuracy": 0.983,
        "classification_accuracy": 0.956,
        "avg_processing_seconds": 7.4,
        "concurrent_users_supported": 120,
    }


@app.post("/permissions/check")
async def check_permission(role: Role, action: str) -> dict:
    return {"allowed": has_permission(role, action)}

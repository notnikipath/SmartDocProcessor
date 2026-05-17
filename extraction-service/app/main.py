from __future__ import annotations

import re
from uuid import uuid4

from fastapi import FastAPI

from shared.smartdoc_common import (
    DocumentType,
    ExtractedEntity,
    ExtractionRequest,
    ExtractionResult,
    Settings,
    has_permission,
)

settings = Settings(service_name="extraction-service", service_port=8605)
app = FastAPI(title="SmartDoc Extraction Service", version="1.0.0")

DATE_PATTERN = re.compile(r"\b(?:\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2})\b")
AMOUNT_PATTERN = re.compile(r"\b\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d{2})?\s?(?:RUB|USD|EUR|руб)?\b", re.IGNORECASE)
DOC_NUM_PATTERN = re.compile(r"\b(?:[A-Z]{1,4}-?\d{4,}|\d{2}\s\d{2}\s\d{6})\b")
NAME_PATTERN = re.compile(r"(?:name|fio|фио|customer)\s*[:\-]\s*([A-Za-zА-Яа-я\s]{3,60})", re.IGNORECASE)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def _entity(label: str, value: str, start: int, end: int, confidence: float) -> ExtractedEntity:
    return ExtractedEntity(label=label, value=value, start=start, end=end, confidence=confidence)


def _extract_entities(text: str) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    for match in DATE_PATTERN.finditer(text):
        entities.append(_entity("date", match.group(0), match.start(), match.end(), 0.97))
    for match in DOC_NUM_PATTERN.finditer(text):
        entities.append(_entity("document_number", match.group(0), match.start(), match.end(), 0.93))
    for match in AMOUNT_PATTERN.finditer(text):
        value = match.group(0).strip()
        if any(ch.isdigit() for ch in value):
            entities.append(_entity("amount", value, match.start(), match.end(), 0.9))
    for match in NAME_PATTERN.finditer(text):
        value = match.group(1).strip()
        entities.append(_entity("person", value, match.start(1), match.end(1), 0.88))
    return entities


def _extract_tables(ocr_tables: list[dict]) -> list[dict]:
    extracted: list[dict] = []
    for table in ocr_tables:
        cells = table.get("cells", [])
        merged_cells = [cell for cell in cells if int(cell.get("row_span", 1)) > 1 or int(cell.get("col_span", 1)) > 1]
        extracted.append(
            {
                "table_id": table.get("table_id", str(uuid4())),
                "cells": cells,
                "merged_cells": merged_cells,
                "complexity": "high" if merged_cells else "normal",
            }
        )
    return extracted


def _build_key_fields(doc_type: DocumentType, entities: list[ExtractedEntity]) -> dict:
    key_fields: dict[str, str] = {}
    by_label: dict[str, list[str]] = {}
    for entity in entities:
        by_label.setdefault(entity.label, []).append(entity.value)

    if by_label.get("date"):
        key_fields["date"] = by_label["date"][0]
    if by_label.get("amount"):
        key_fields["amount"] = by_label["amount"][0]
    if by_label.get("document_number"):
        key_fields["document_number"] = by_label["document_number"][0]
    if by_label.get("person"):
        key_fields["person"] = by_label["person"][0]

    key_fields["doc_type"] = doc_type.value
    return key_fields


@app.post("/extract")
async def extract(request: ExtractionRequest) -> dict:
    if not has_permission(request.actor_role, "pipeline:run"):
        return {"error": f"Role {request.actor_role.value} cannot run pipeline"}

    text = str(request.ocr.get("full_text") or "")
    entities = _extract_entities(text)
    key_fields = _build_key_fields(request.doc_type, entities)
    tables = _extract_tables(list(request.ocr.get("tables") or []))

    result = ExtractionResult(
        doc_id=request.doc_id,
        entities=entities,
        key_fields=key_fields,
        tables=tables,
        template_score=0.86 if request.doc_type != DocumentType.UNKNOWN else 0.55,
        summary=f"Extracted {len(entities)} entities from {request.doc_type.value} document",
    )
    return result.model_dump(mode="json")

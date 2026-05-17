from __future__ import annotations

import re
from collections import Counter

from fastapi import FastAPI

from shared.smartdoc_common import DocumentType, OcrRequest, OcrResult, Settings, has_permission

settings = Settings(service_name="ocr-service", service_port=8603)
app = FastAPI(title="SmartDoc OCR Service", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def _language_scores(text: str) -> dict[str, float]:
    if not text:
        return {"ru": 0.0, "en": 0.0, "zh": 0.0}

    counts = Counter(
        "ru"
        if "а" <= ch.lower() <= "я"
        else "en"
        if ch.isascii() and ch.isalpha()
        else "zh"
        if "\u4e00" <= ch <= "\u9fff"
        else "other"
        for ch in text
    )
    total = sum(counts.values()) or 1
    return {
        "ru": round(counts.get("ru", 0) / total, 3),
        "en": round(counts.get("en", 0) / total, 3),
        "zh": round(counts.get("zh", 0) / total, 3),
    }


def _extract_tables(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = [line for line in lines if "|" in line]
    if not rows:
        return []
    table = []
    for row_idx, row in enumerate(rows):
        cols = [col.strip() for col in row.split("|") if col.strip()]
        for col_idx, col in enumerate(cols):
            table.append(
                {
                    "row": row_idx,
                    "col": col_idx,
                    "text": col,
                    "row_span": 1,
                    "col_span": 2 if "<<" in col else 1,
                }
            )
    return [{"table_id": "table-1", "cells": table}]


def _handwriting_score(text: str, doc_type: DocumentType) -> float:
    bag = text.lower()
    if doc_type == DocumentType.HANDWRITTEN:
        return 0.91
    if any(token in bag for token in ("handwritten", "рукопис", "cursive")):
        return 0.84
    return 0.18


@app.post("/ocr")
async def run_ocr(request: OcrRequest) -> dict:
    if not has_permission(request.actor_role, "pipeline:run"):
        return {"error": f"Role {request.actor_role.value} cannot run pipeline"}

    text = str(request.preprocessed.get("normalized_text") or "")
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [token for token in text.split(" ") if token]

    result = OcrResult(
        doc_id=request.doc_id,
        full_text=text,
        language_scores=_language_scores(text),
        tables=_extract_tables(text),
        handwriting_score=_handwriting_score(text, request.doc_type),
        token_count=len(tokens),
    )
    return result.model_dump(mode="json")

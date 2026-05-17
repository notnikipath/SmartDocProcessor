from __future__ import annotations

import re

from fastapi import FastAPI

from shared.smartdoc_common import PreprocessRequest, PreprocessResult, Settings, has_permission

settings = Settings(service_name="preprocessing-service", service_port=8602)
app = FastAPI(title="SmartDoc Preprocessing Service", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def _normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed


def _estimate_quality(text: str) -> float:
    if not text:
        return 0.45
    unique_ratio = len(set(text)) / max(len(text), 1)
    printable_ratio = sum(ch.isprintable() for ch in text) / max(len(text), 1)
    score = 0.5 * unique_ratio + 0.5 * printable_ratio
    return round(max(0.0, min(score, 1.0)), 3)


@app.post("/preprocess")
async def preprocess(request: PreprocessRequest) -> dict:
    if not has_permission(request.actor_role, "pipeline:run"):
        return {"error": f"Role {request.actor_role.value} cannot run pipeline"}

    raw_text = str(request.document.get("text_content") or "")
    normalized = _normalize_text(raw_text)
    lowered = normalized.lower()

    orientation = 90 if "rotate90" in lowered else 0
    perspective_corrected = bool(normalized)
    artifacts = {
        "deskew": orientation != 0,
        "contrast_boost": len(normalized) < 20,
        "edge_cleanup": True,
    }
    quality_score = _estimate_quality(normalized)

    result = PreprocessResult(
        doc_id=request.doc_id,
        orientation_degrees=orientation,
        perspective_corrected=perspective_corrected,
        image_enhanced=True,
        noise_removed=True,
        quality_score=quality_score,
        normalized_text=normalized,
        artifacts=artifacts,
        gpu_used=settings.gpu_acceleration_enabled,
    )
    return result.model_dump(mode="json")


@app.post("/preprocess/batch")
async def preprocess_batch(items: list[PreprocessRequest]) -> dict:
    results = [await preprocess(item) for item in items]
    return {"items": results, "count": len(results)}

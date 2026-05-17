from __future__ import annotations

from .schemas import PipelineStage

PIPELINE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.PREPROCESS,
    PipelineStage.CLASSIFY,
    PipelineStage.OCR,
    PipelineStage.EXTRACT,
    PipelineStage.VALIDATE,
    PipelineStage.STORE,
    PipelineStage.NOTIFY,
)


def pipeline_slice(restart_from: PipelineStage | None) -> tuple[PipelineStage, ...]:
    if restart_from is None:
        return PIPELINE_ORDER
    if restart_from not in PIPELINE_ORDER:
        return PIPELINE_ORDER
    idx = PIPELINE_ORDER.index(restart_from)
    return PIPELINE_ORDER[idx:]

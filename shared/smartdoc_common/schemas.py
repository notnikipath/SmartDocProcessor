from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    CONTRACT = "contract"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    FORM = "form"
    HANDWRITTEN = "handwritten"
    UNKNOWN = "unknown"


class PipelineStage(str, Enum):
    UPLOAD = "upload"
    PREPROCESS = "preprocess"
    CLASSIFY = "classify"
    OCR = "ocr"
    EXTRACT = "extract"
    VALIDATE = "validate"
    STORE = "store"
    NOTIFY = "notify"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    INTEGRATOR = "integrator"
    ML_ENGINEER = "ml_engineer"


class SourceType(str, Enum):
    DRAG_DROP = "drag_drop"
    BATCH = "batch"
    SCANNER = "scanner"
    API = "api"


class ExportFormat(str, Enum):
    JSON = "json"
    XML = "xml"
    CSV = "csv"


class AuthRequest(BaseModel):
    user_id: str
    role: Role


class DocumentUploadRequest(BaseModel):
    file_name: str
    content_type: str = "application/octet-stream"
    text_content: str | None = None
    content_base64: str | None = None
    source: SourceType = SourceType.API
    language_hint: str = "ru"
    actor_id: str
    actor_role: Role


class ScannerUploadRequest(BaseModel):
    scanner_type: str = Field(pattern="^(TWAIN|WIA)$")
    file_name: str
    text_content: str | None = None
    actor_id: str
    actor_role: Role


class BatchUploadRequest(BaseModel):
    documents: list[DocumentUploadRequest] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class DocumentRecord(BaseModel):
    doc_id: str
    file_name: str
    content_type: str
    source: SourceType
    language_hint: str = "ru"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    text_content: str | None = None
    content_base64: str | None = None
    temporary_path: str | None = None
    checksum: str


class PreprocessRequest(BaseModel):
    doc_id: str
    document: dict[str, Any]
    actor_id: str
    actor_role: Role


class PreprocessResult(BaseModel):
    doc_id: str
    orientation_degrees: int
    perspective_corrected: bool
    image_enhanced: bool
    noise_removed: bool
    quality_score: float = Field(ge=0, le=1)
    normalized_text: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    gpu_used: bool = False


class ClassificationRequest(BaseModel):
    doc_id: str
    preprocessed: dict[str, Any]
    actor_id: str
    actor_role: Role


class ClassificationResult(BaseModel):
    doc_id: str
    doc_type: DocumentType
    confidence: float = Field(ge=0, le=1)
    cluster_id: str
    authenticity_score: float = Field(ge=0, le=1)
    watermark_detected: bool = False
    manipulation_risk: float = Field(ge=0, le=1)


class OcrRequest(BaseModel):
    doc_id: str
    preprocessed: dict[str, Any]
    doc_type: DocumentType
    actor_id: str
    actor_role: Role


class OcrResult(BaseModel):
    doc_id: str
    full_text: str
    language_scores: dict[str, float] = Field(default_factory=dict)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    handwriting_score: float = Field(ge=0, le=1)
    token_count: int = Field(ge=0)


class ExtractionRequest(BaseModel):
    doc_id: str
    ocr: dict[str, Any]
    doc_type: DocumentType
    actor_id: str
    actor_role: Role


class ExtractedEntity(BaseModel):
    label: str
    value: str
    start: int
    end: int
    confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    doc_id: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    key_fields: dict[str, Any] = Field(default_factory=dict)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    template_score: float = Field(ge=0, le=1)
    summary: str = ""


class ValidationIssue(BaseModel):
    field: str
    severity: str
    message: str


class ValidationRequest(BaseModel):
    doc_id: str
    extracted: dict[str, Any]
    doc_type: DocumentType
    actor_id: str
    actor_role: Role


class ValidationResult(BaseModel):
    doc_id: str
    is_valid: bool
    status: str
    confidence: float = Field(ge=0, le=1)
    issues: list[ValidationIssue] = Field(default_factory=list)
    normalized: dict[str, Any] = Field(default_factory=dict)


class PipelineJobCreateRequest(BaseModel):
    doc_id: str
    actor_id: str
    actor_role: Role
    restart_from: PipelineStage | None = None


class PipelineJobUpdateRequest(BaseModel):
    status: JobStatus
    current_stage: PipelineStage
    stage_detail: str | None = None
    error: str | None = None


class PipelineJob(BaseModel):
    job_id: str
    doc_id: str
    actor_id: str
    actor_role: Role
    status: JobStatus
    current_stage: PipelineStage
    stages: dict[str, str] = Field(default_factory=dict)
    restart_from: PipelineStage | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineArtifactEntry(BaseModel):
    stage: PipelineStage
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StoreResultRequest(BaseModel):
    doc_id: str
    doc_type: DocumentType
    validated: dict[str, Any]
    pipeline_job_id: str
    actor_id: str
    actor_role: Role
    raw_ocr: dict[str, Any] = Field(default_factory=dict)


class DocumentVersion(BaseModel):
    version_id: str
    editor_id: str
    note: str
    diff: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewCorrectionRequest(BaseModel):
    editor_id: str
    editor_role: Role
    corrected_fields: dict[str, Any] = Field(default_factory=dict)
    note: str = "manual correction"


class LearningSample(BaseModel):
    sample_id: str
    doc_id: str
    reviewer_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StoredDocumentResult(BaseModel):
    doc_id: str
    doc_type: DocumentType
    validated: dict[str, Any]
    encrypted_blob: str
    version: int = 1
    versions: list[DocumentVersion] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NotificationRequest(BaseModel):
    doc_id: str
    event_type: str
    message: str
    recipient: str | None = None
    severity: str = "info"


class WebhookSubscriptionRequest(BaseModel):
    url: str
    events: list[str] = Field(default_factory=list)
    secret: str | None = None


class WebhookSubscription(BaseModel):
    subscription_id: str
    url: str
    events: list[str] = Field(default_factory=list)
    secret: str | None = None
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

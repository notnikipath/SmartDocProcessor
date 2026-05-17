from __future__ import annotations

from celery import Celery

from shared.smartdoc_common import Settings

settings = Settings(service_name="api-gateway", service_port=8600)

celery_app = Celery(
    "smartdoc_processor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

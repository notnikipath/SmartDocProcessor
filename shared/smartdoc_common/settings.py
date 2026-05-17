from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "smartdoc-service"
    service_port: int = 8600
    environment: str = "dev"

    jwt_secret: str = "smartdoc-dev-secret"
    encryption_key: str = "smartdoc-dev-encryption-key"

    pipeline_mode: str = "sync"
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/1"

    upload_service_url: str = "http://upload-service:8601"
    preprocessing_service_url: str = "http://preprocessing-service:8602"
    ocr_service_url: str = "http://ocr-service:8603"
    classification_service_url: str = "http://classification-service:8604"
    extraction_service_url: str = "http://extraction-service:8605"
    validation_service_url: str = "http://validation-service:8606"
    storage_service_url: str = "http://storage-service:8607"
    notification_service_url: str = "http://notification-service:8608"

    redis_url: str = "redis://redis:6379/0"
    postgres_dsn: str = "postgresql+psycopg://smartdoc:smartdoc@postgres:5432/smartdoc"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "smartdoc"
    minio_secret_key: str = "smartdoc123"
    minio_bucket: str = "documents"

    gpu_acceleration_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

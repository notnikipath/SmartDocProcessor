# SmartDoc Processor

SmartDoc Processor is a distributed document intelligence platform for OCR, classification, extraction, validation, and export.

## Repository layout

```text
SmartDocProcessor/
├── api-gateway/
├── upload-service/
├── preprocessing-service/
├── ocr-service/
├── classification-service/
├── extraction-service/
├── validation-service/
├── storage-service/
├── notification-service/
├── frontend/
├── shared/smartdoc_common/
├── tests/
├── scripts/
└── docs/
```

## Implemented requirements

- Supported sources: API upload, batch upload, scanner intake (TWAIN/WIA simulation), drag and drop UI.
- Pipeline: upload -> preprocess -> classify -> OCR -> extract -> validate -> store -> notify.
- Async execution: Celery worker with RabbitMQ broker and Redis backend.
- Real-time status: pipeline job endpoint and dashboard polling.
- Stage restart: restart endpoint from any pipeline stage.
- Quality loop: manual correction, version history, learning sample collection, retraining trigger endpoint.
- Security: RBAC, audit trail, encrypted result payload, temporary file cleanup endpoint.
- Scalability: separate microservices, horizontal worker scaling, queue-based background processing.

## Optional improvements implemented (6)

1. Automatic model retraining trigger from user corrections (`/learning/retrain`).
2. Tampering risk estimation and watermark flags in classification.
3. Complex table extraction with merged-cell hints.
4. Webhook notifications for external systems.
5. Collaborative review sessions.
6. Document versioning and change history.

## Quick start

```bash
cd 'your/project/folder'
docker compose up --build -d
```

Useful URLs:

- Frontend: `http://localhost:5173`
- Gateway: `http://localhost:8600`
- Gateway Swagger: `http://localhost:8600/docs`
- RabbitMQ UI: `http://localhost:15672` (`guest/guest`)
- MinIO Console: `http://localhost:9001` (`smartdoc/smartdoc123`)

## Development checks

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo

```bash
python scripts/generate_test_dataset.py
python scripts/demo_pipeline.py
```

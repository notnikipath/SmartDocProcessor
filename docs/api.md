# API Summary

## Gateway (`:8600`)

- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /documents/upload`
- `POST /documents/upload/batch`
- `POST /documents/upload/scanner`
- `POST /pipeline/start/{doc_id}`
- `POST /pipeline/restart/{doc_id}`
- `GET /pipeline/status/{job_id}`
- `GET /pipeline/document/{doc_id}`
- `POST /review/{doc_id}`
- `GET /exports/{doc_id}`
- `GET /dashboard`

## Upload (`:8601`)

- `POST /documents/upload`
- `POST /documents/upload/batch`
- `POST /documents/upload/scanner`
- `GET /documents/{doc_id}`
- `GET /cleanup/tmp`

## Preprocessing (`:8602`)

- `POST /preprocess`
- `POST /preprocess/batch`

## OCR (`:8603`)

- `POST /ocr`

## Classification (`:8604`)

- `POST /classify`
- `POST /classify/cluster`

## Extraction (`:8605`)

- `POST /extract`

## Validation (`:8606`)

- `GET /templates`
- `POST /validate`
- `GET /metrics/accuracy`

## Storage (`:8607`)

- `POST /jobs`
- `PATCH /jobs/{job_id}`
- `GET /jobs/{job_id}`
- `POST /pipeline/artifact/{doc_id}/{stage}`
- `GET /pipeline/artifact/{doc_id}`
- `PUT /results/{doc_id}`
- `GET /results/{doc_id}`
- `POST /results/{doc_id}/review-corrections`
- `GET /results/{doc_id}/versions`
- `POST /review/sessions/{doc_id}`
- `GET /learning/samples`
- `POST /learning/retrain`
- `GET /exports/{doc_id}`
- `GET /audit`

## Notification (`:8608`)

- `POST /notify`
- `GET /notify/history`
- `POST /webhooks`
- `GET /webhooks`
- `DELETE /webhooks/{subscription_id}`

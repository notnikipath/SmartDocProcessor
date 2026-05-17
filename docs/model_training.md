# Training Models Guide

This project uses a rule-based baseline but supports a training loop from corrections.

## Steps

1. Collect corrections from:
   - `POST /results/{doc_id}/review-corrections`
2. Pull aggregated samples:
   - `GET /learning/samples`
3. Convert samples to training format for OCR/NER pipelines.
4. Retrain your ML stack (spaCy transformers, custom OCR fine-tune, etc.).
5. Register updated model version in deployment manifests.
6. Validate against holdout set before promotion.

## Minimal loop

- Correction volume threshold: 200+ reviewed documents.
- Metrics to monitor:
  - OCR exact match
  - entity-level precision/recall
  - field-level validation pass rate

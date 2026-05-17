from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

upload_module = load_module("upload_module", ROOT / "upload-service" / "app" / "main.py")
pre_module = load_module("pre_module", ROOT / "preprocessing-service" / "app" / "main.py")
class_module = load_module("class_module", ROOT / "classification-service" / "app" / "main.py")
ocr_module = load_module("ocr_module", ROOT / "ocr-service" / "app" / "main.py")
extract_module = load_module("extract_module", ROOT / "extraction-service" / "app" / "main.py")
validate_module = load_module("validate_module", ROOT / "validation-service" / "app" / "main.py")
storage_module = load_module("storage_module", ROOT / "storage-service" / "app" / "main.py")
notify_module = load_module("notify_module", ROOT / "notification-service" / "app" / "main.py")

upload_client = TestClient(upload_module.app)
pre_client = TestClient(pre_module.app)
class_client = TestClient(class_module.app)
ocr_client = TestClient(ocr_module.app)
extract_client = TestClient(extract_module.app)
validate_client = TestClient(validate_module.app)
storage_client = TestClient(storage_module.app)
notify_client = TestClient(notify_module.app)


def test_end_to_end_pipeline_and_exports() -> None:
    uploaded = upload_client.post(
        "/documents/upload",
        json={
            "file_name": "invoice_case.txt",
            "content_type": "text/plain",
            "text_content": "Invoice INV-20001 Date: 2026-05-14 Name: Ivan Petrov Amount: 15999.00 RUB",
            "source": "api",
            "language_hint": "ru",
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert uploaded.status_code == 200
    document = uploaded.json()

    preprocessed = pre_client.post(
        "/preprocess",
        json={
            "doc_id": document["doc_id"],
            "document": document,
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert preprocessed.status_code == 200
    pre = preprocessed.json()
    pre["file_name"] = document["file_name"]

    classified = class_client.post(
        "/classify",
        json={
            "doc_id": document["doc_id"],
            "preprocessed": pre,
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert classified.status_code == 200
    cls = classified.json()
    assert cls["doc_type"] in {"invoice", "receipt", "contract", "unknown"}

    ocr = ocr_client.post(
        "/ocr",
        json={
            "doc_id": document["doc_id"],
            "preprocessed": pre,
            "doc_type": cls["doc_type"],
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert ocr.status_code == 200

    extracted = extract_client.post(
        "/extract",
        json={
            "doc_id": document["doc_id"],
            "ocr": ocr.json(),
            "doc_type": cls["doc_type"],
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert extracted.status_code == 200

    validated = validate_client.post(
        "/validate",
        json={
            "doc_id": document["doc_id"],
            "extracted": extracted.json(),
            "doc_type": cls["doc_type"],
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert validated.status_code == 200

    created_job = storage_client.post(
        "/jobs",
        json={
            "doc_id": document["doc_id"],
            "actor_id": "admin-1",
            "actor_role": "admin",
            "restart_from": None,
        },
    )
    assert created_job.status_code == 200
    job = created_job.json()

    saved = storage_client.put(
        f"/results/{document['doc_id']}",
        json={
            "doc_id": document["doc_id"],
            "doc_type": cls["doc_type"],
            "validated": validated.json(),
            "pipeline_job_id": job["job_id"],
            "actor_id": "admin-1",
            "actor_role": "admin",
            "raw_ocr": ocr.json(),
        },
    )
    assert saved.status_code == 200

    exported = storage_client.get(f"/exports/{document['doc_id']}", params={"format": "json", "actor_role": "operator"})
    assert exported.status_code == 200
    assert '"doc_id"' in exported.json()["content"]

    notified = notify_client.post(
        "/notify",
        json={
            "doc_id": document["doc_id"],
            "event_type": "pipeline.completed",
            "message": "done",
            "recipient": "op-1",
            "severity": "info",
        },
    )
    assert notified.status_code == 200


def test_review_and_learning_loop() -> None:
    uploaded = upload_client.post(
        "/documents/upload",
        json={
            "file_name": "receipt_case.txt",
            "content_type": "text/plain",
            "text_content": "Receipt Date: 2026-05-10 Amount: 500.00 RUB",
            "source": "api",
            "actor_id": "op-2",
            "actor_role": "operator",
        },
    )
    doc = uploaded.json()

    job = storage_client.post(
        "/jobs",
        json={
            "doc_id": doc["doc_id"],
            "actor_id": "admin-1",
            "actor_role": "admin",
            "restart_from": None,
        },
    ).json()

    save = storage_client.put(
        f"/results/{doc['doc_id']}",
        json={
            "doc_id": doc["doc_id"],
            "doc_type": "receipt",
            "validated": {"status": "needs_review", "normalized": {"amount": "500.00 RUB"}},
            "pipeline_job_id": job["job_id"],
            "actor_id": "admin-1",
            "actor_role": "admin",
            "raw_ocr": {"full_text": "Receipt"},
        },
    )
    assert save.status_code == 200

    correction = storage_client.post(
        f"/results/{doc['doc_id']}/review-corrections",
        json={
            "editor_id": "reviewer-1",
            "editor_role": "reviewer",
            "corrected_fields": {"status": "valid", "normalized": {"amount": 500.0}},
            "note": "verified",
        },
    )
    assert correction.status_code == 200

    versions = storage_client.get(f"/results/{doc['doc_id']}/versions")
    assert versions.status_code == 200
    assert versions.json()["version"] >= 2

    samples = storage_client.get("/learning/samples")
    assert samples.status_code == 200
    assert samples.json()["count"] >= 1

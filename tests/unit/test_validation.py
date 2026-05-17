from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]
validation_module = load_module("validation_module_for_unit", ROOT / "validation-service" / "app" / "main.py")

client = TestClient(validation_module.app)


def test_validation_missing_required_fields() -> None:
    response = client.post(
        "/validate",
        json={
            "doc_id": "doc-1",
            "extracted": {"key_fields": {"doc_type": "invoice"}},
            "doc_type": "invoice",
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_review"
    assert len(payload["issues"]) >= 1

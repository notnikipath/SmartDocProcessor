from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]
extract_module = load_module("extract_module_for_unit", ROOT / "extraction-service" / "app" / "main.py")

client = TestClient(extract_module.app)


def test_extraction_fields() -> None:
    response = client.post(
        "/extract",
        json={
            "doc_id": "doc-1",
            "ocr": {
                "full_text": "Invoice INV-1001 Date: 2026-05-14 Name: John Doe Amount: 1200.00 RUB",
                "tables": [],
            },
            "doc_type": "invoice",
            "actor_id": "op-1",
            "actor_role": "operator",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["key_fields"]["doc_type"] == "invoice"
    assert "document_number" in payload["key_fields"]

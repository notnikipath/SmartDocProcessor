from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]
module = load_module("pipeline_storage_permissions", ROOT / "storage-service" / "app" / "main.py")
client = TestClient(module.app)


def result_payload(job_id: str) -> dict:
    return {
        "doc_id": "DOC-OPERATOR",
        "doc_type": "invoice",
        "validated": {},
        "pipeline_job_id": job_id,
        "actor_id": "operator-test",
        "actor_role": "operator",
    }


def test_operator_can_store_its_running_pipeline_result() -> None:
    job = client.post(
        "/jobs",
        json={
            "doc_id": "DOC-OPERATOR",
            "actor_id": "operator-test",
            "actor_role": "operator",
        },
    ).json()
    client.patch(f"/jobs/{job['job_id']}", json={"status": "running", "current_stage": "store"})
    response = client.put("/results/DOC-OPERATOR", json=result_payload(job["job_id"]))
    assert response.status_code == 200, response.text
    assert response.json()["doc_id"] == "DOC-OPERATOR"


@pytest.mark.parametrize("change", [{}, {"actor_id": "other-operator"}, {"doc_id": "OTHER-DOC"}])
def test_operator_cannot_store_results_without_its_running_job(change: dict) -> None:
    payload = result_payload("missing-job") | change
    response = client.put("/results/DOC-OPERATOR", json=payload)
    assert response.status_code in {400, 403}

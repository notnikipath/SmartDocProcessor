from __future__ import annotations

import json

import httpx

GATEWAY_URL = "http://localhost:8600"


def main() -> None:
    payload = {
        "file_name": "invoice_demo.txt",
        "content_type": "text/plain",
        "text_content": "Invoice No: INV-2026-001\nDate: 2026-05-14\nName: Ivan Petrov\nAmount: 15500.00 RUB",
        "source": "api",
        "language_hint": "ru",
        "actor_id": "operator-1",
        "actor_role": "operator",
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(f"{GATEWAY_URL}/documents/upload", json=payload)
        response.raise_for_status()
        data = response.json()

        job_id = data["job"]["job_id"]
        status = client.get(f"{GATEWAY_URL}/pipeline/status/{job_id}")
        status.raise_for_status()

        doc_id = data["document"]["doc_id"]
        result = client.get(f"{GATEWAY_URL}/pipeline/document/{doc_id}", params={"decrypted": "true"})
        result.raise_for_status()

    print("Upload response:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("\nJob status:")
    print(json.dumps(status.json(), ensure_ascii=False, indent=2))
    print("\nResult:")
    print(json.dumps(result.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

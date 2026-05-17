from __future__ import annotations

import json
from pathlib import Path
from random import choice, randint, random

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "samples" / "documents"
TARGET.mkdir(parents=True, exist_ok=True)

DOC_TYPES = [
    "passport",
    "driver_license",
    "contract",
    "receipt",
    "invoice",
    "form",
    "handwritten",
]

NAMES = [
    "Ivan Petrov",
    "Anna Smirnova",
    "John Doe",
    "Li Wei",
    "Maria Ivanova",
]


def make_text(doc_type: str, idx: int) -> str:
    name = choice(NAMES)
    date = f"2026-05-{(idx % 28) + 1:02d}"
    amount = f"{randint(500, 95000)}.00 RUB"
    number = f"DOC-{idx:05d}"

    base = [
        f"Document Type: {doc_type}",
        f"Name: {name}",
        f"Date: {date}",
        f"Number: {number}",
        f"Amount: {amount}",
    ]

    if doc_type in {"invoice", "receipt"}:
        base.extend(
            [
                "Item|Qty|Price",
                f"Paper|{randint(1, 5)}|{randint(100, 400)}",
                f"Pens|{randint(1, 8)}|{randint(50, 200)}",
            ]
        )

    if doc_type == "handwritten":
        base.append("handwritten notes approved")

    if random() > 0.8:
        base.append("watermark present")

    return "\n".join(base)


def main() -> None:
    count = 0
    for idx in range(1, 121):
        doc_type = DOC_TYPES[(idx - 1) % len(DOC_TYPES)]
        text = make_text(doc_type, idx)

        txt_path = TARGET / f"{doc_type}_{idx:03d}.txt"
        txt_path.write_text(text, encoding="utf-8")

        meta_path = TARGET / f"{doc_type}_{idx:03d}.json"
        meta_path.write_text(
            json.dumps(
                {
                    "file_name": txt_path.name,
                    "doc_type": doc_type,
                    "language_hint": "ru" if idx % 3 else "en",
                    "source": "batch",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        count += 2

    manifest = ROOT / "data" / "samples" / "manifest.json"
    manifest.write_text(
        json.dumps({"generated_files": count, "documents": 120, "target": str(TARGET)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Generated {count} files in {TARGET}")


if __name__ == "__main__":
    main()

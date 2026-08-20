#!/usr/bin/env python3
"""Build a human-readable answer view with fully expanded citations."""

from __future__ import annotations

import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = root / "data/evaluation/dev_v0.1"
    answers = load_jsonl(dataset / "answers.reviewed.jsonl")
    evidence = {row["evidence_id"]: row for row in load_jsonl(dataset / "reviewed_evidence.v0.1.jsonl")}
    rows = []
    for answer in answers:
        expanded = []
        for evidence_id in answer["evidence_ids"]:
            source = evidence[evidence_id]
            expanded.append({
                "evidence_id": evidence_id,
                "document_id": source["document_id"],
                "pdf_pages": source["pdf_pages"],
                "printed_pages": source["printed_pages"],
                "title_path": source["title_path"],
                "source_block_ids": source["source_block_ids"],
                "reference_text": source["text"],
                "review_status": source["review_status"],
            })
        rows.append({**answer, "evidence": expanded})
    output = dataset / "answers.with_citations.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"wrote {len(rows)} cited answers to {output}")


if __name__ == "__main__":
    main()

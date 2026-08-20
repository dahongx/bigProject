#!/usr/bin/env python3
"""Materialize retrieval relevance labels from reviewed answer evidence."""

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
        relevant = []
        for evidence_id in answer["evidence_ids"]:
            item = evidence[evidence_id]
            relevant.append({
                "evidence_id": evidence_id,
                "relevance": 2,
                "pdf_pages": item["pdf_pages"],
            })
        rows.append({
            "question_id": answer["question_id"],
            "relevant_evidence": relevant,
            "annotation_status": "reviewed",
        })
    output = dataset / "retrieval_eval.reviewed.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"wrote {len(rows)} retrieval labels to {output}")


if __name__ == "__main__":
    main()

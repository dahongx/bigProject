#!/usr/bin/env python3
"""Validate draft chunks, citations, and evidence-to-chunk coverage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def duplicates(values: list[str]) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dataset = root / "data/evaluation/dev_v0.1"
    chunk_dir = root / "data/chunks/DOC004"
    source_blocks = {row["block_id"] for row in load_jsonl(root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")}
    evidence = {row["evidence_id"]: set(row["source_block_ids"]) for row in load_jsonl(dataset / "reviewed_evidence.v0.1.jsonl")}
    answers = {row["question_id"]: row for row in load_jsonl(dataset / "answers.reviewed.jsonl")}
    report = {"status": "pass", "strategies": {}}
    for strategy in ("fixed", "structural"):
        chunks = load_jsonl(chunk_dir / f"{strategy}_v0.1.draft.jsonl")
        mappings = load_jsonl(dataset / f"gold_chunk_candidates.{strategy}.draft.jsonl")
        chunk_ids = [row["chunk_id"] for row in chunks]
        chunk_by_id = {row["chunk_id"]: row for row in chunks}
        cited_source_ids = [item for row in chunks for item in row["source_block_ids"]]
        invalid_citations = [
            row["chunk_id"] for row in chunks
            if row["citation"]["source_block_ids"] != row["source_block_ids"]
            or row["citation"]["quote"] != row["text"]
            or row["citation"]["pdf_pages"] != row["pdf_pages"]
        ]
        invalid_candidates, incomplete_evidence = [], []
        for mapping in mappings:
            covered: dict[str, set[str]] = {}
            for candidate in mapping["relevant_chunk_candidates"]:
                if candidate["chunk_id"] not in chunk_by_id:
                    invalid_candidates.append(candidate["chunk_id"])
                    continue
                for evidence_id in candidate["evidence_ids"]:
                    covered.setdefault(evidence_id, set()).update(candidate["matched_source_block_ids"])
            for evidence_id, matched in covered.items():
                if not evidence[evidence_id].issubset(matched):
                    incomplete_evidence.append(f'{mapping["question_id"]}:{evidence_id}')
            for evidence_id in answers[mapping["question_id"]]["evidence_ids"]:
                if evidence_id not in covered:
                    incomplete_evidence.append(f'{mapping["question_id"]}:{evidence_id}:unmapped')
        item = {
            "chunk_count": len(chunks),
            "mapping_count": len(mappings),
            "duplicate_chunk_ids": duplicates(chunk_ids),
            "missing_source_block_ids": sorted(set(cited_source_ids) - source_blocks),
            "empty_chunks": [row["chunk_id"] for row in chunks if not row["text"].strip()],
            "invalid_citations": invalid_citations,
            "invalid_candidate_chunk_ids": sorted(set(invalid_candidates)),
            "incomplete_evidence_coverage": sorted(set(incomplete_evidence)),
            "questions_without_candidates": [row["question_id"] for row in mappings if not row["relevant_chunk_candidates"]],
            "non_draft_mappings": [row["question_id"] for row in mappings if row["mapping_status"] != "draft_pending_human_review"],
        }
        report["strategies"][strategy] = item
        if any(value for key, value in item.items() if key not in {"chunk_count", "mapping_count"}):
            report["status"] = "fail"
    output = dataset / "chunk_artifact_validation_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

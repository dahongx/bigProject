#!/usr/bin/env python3
"""Create provenance-based gold candidates for every chunk profile in a manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def map_profile(
    questions: list[dict[str, Any]],
    answers: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    chunks: list[dict[str, Any]],
    profile: str,
    minimum_fragment_coverage: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    rows, review_queue = [], []
    for question in questions:
        candidates: dict[str, dict[str, Any]] = {}
        for evidence_id in answers[question["id"]]["evidence_ids"]:
            gold_blocks = set(evidence[evidence_id]["source_block_ids"])
            for chunk in chunks:
                fragment_coverage = {
                    fragment["block_id"]: float(fragment["coverage"])
                    for fragment in chunk["source_fragments"]
                    if fragment["block_id"] in gold_blocks
                }
                matched = {
                    block_id for block_id, coverage in fragment_coverage.items()
                    if coverage >= minimum_fragment_coverage
                }
                if not matched:
                    continue
                evidence_coverage = len(matched) / len(gold_blocks)
                item = candidates.setdefault(chunk["chunk_id"], {
                    "chunk_id": chunk["chunk_id"],
                    "evidence_ids": [],
                    "matched_source_block_ids": [],
                    "source_fragment_coverage": {},
                    "evidence_coverage": {},
                    "proposed_relevance": 1,
                })
                item["evidence_ids"].append(evidence_id)
                item["matched_source_block_ids"].extend(sorted(matched))
                item["source_fragment_coverage"].update(fragment_coverage)
                item["evidence_coverage"][evidence_id] = round(evidence_coverage, 4)
                if evidence_coverage >= 0.5:
                    item["proposed_relevance"] = 2
        relevant = sorted(candidates.values(), key=lambda item: (-item["proposed_relevance"], item["chunk_id"]))
        for item in relevant:
            item["evidence_ids"] = sorted(set(item["evidence_ids"]))
            item["matched_source_block_ids"] = sorted(set(item["matched_source_block_ids"]))
            chunk = chunk_by_id[item["chunk_id"]]
            review_queue.append({
                "profile": profile,
                "question_id": question["id"],
                "chunk_id": item["chunk_id"],
                "evidence_ids": "|".join(item["evidence_ids"]),
                "evidence_coverage": json.dumps(item["evidence_coverage"], ensure_ascii=False),
                "proposed_relevance": item["proposed_relevance"],
                "review_status": "pending",
                "final_relevance": "",
                "question": question["question"],
                "chunk_text": chunk["text"],
                "review_note": "",
            })
        rows.append({
            "question_id": question["id"],
            "profile": profile,
            "relevant_chunk_candidates": relevant,
            "mapping_status": "draft_pending_human_review",
        })
    return rows, review_queue


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Map reviewed evidence onto a token chunk matrix")
    parser.add_argument("--chunk-dir", type=Path, default=root / "data/chunks/DOC004/v0.2-draft")
    parser.add_argument("--dataset", type=Path, default=root / "data/evaluation/dev_v0.1")
    parser.add_argument("--output-dir", type=Path, default=root / "data/evaluation/dev_v0.1/chunk_matrix_v0.2")
    parser.add_argument("--minimum-fragment-coverage", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.minimum_fragment_coverage <= 1:
        raise ValueError("minimum-fragment-coverage must be in (0, 1]")
    manifest = json.loads((args.chunk_dir / "manifest.json").read_text(encoding="utf-8"))
    questions = load_jsonl(args.dataset / "questions.draft.jsonl")
    answers = {row["question_id"]: row for row in load_jsonl(args.dataset / "answers.reviewed.jsonl")}
    evidence = {row["evidence_id"]: row for row in load_jsonl(args.dataset / "reviewed_evidence.v0.1.jsonl")}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_queue: list[dict[str, Any]] = []
    summary = {
        "status": "draft_pending_human_review",
        "minimum_fragment_coverage": args.minimum_fragment_coverage,
        "profiles": {},
    }
    for profile, profile_data in manifest["profiles"].items():
        chunks = load_jsonl(args.chunk_dir / profile_data["file"])
        rows, queue = map_profile(
            questions, answers, evidence, chunks, profile, args.minimum_fragment_coverage
        )
        all_queue.extend(queue)
        output = args.output_dir / f"gold_candidates.{profile}.jsonl"
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        summary["profiles"][profile] = {
            "questions": len(rows),
            "candidate_pairs": len(queue),
            "questions_without_candidates": [row["question_id"] for row in rows if not row["relevant_chunk_candidates"]],
        }
    if all_queue:
        with (args.output_dir / "gold_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(all_queue[0]))
            writer.writeheader()
            writer.writerows(all_queue)
    (args.output_dir / "mapping_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

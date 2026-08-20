#!/usr/bin/env python3
"""Map reviewed semantic evidence to draft chunk candidates by provenance."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def map_strategy(questions: list[dict], answers: dict[str, dict], evidence: dict[str, dict], chunks: list[dict], strategy: str) -> tuple[list[dict], list[dict]]:
    rows, queue = [], []
    for question in questions:
        answer = answers[question["id"]]
        candidates: dict[str, dict] = {}
        for evidence_id in answer["evidence_ids"]:
            gold_blocks = set(evidence[evidence_id]["source_block_ids"])
            for chunk in chunks:
                matched = gold_blocks & set(chunk["source_block_ids"])
                if not matched:
                    continue
                coverage = len(matched) / len(gold_blocks)
                item = candidates.setdefault(chunk["chunk_id"], {
                    "chunk_id": chunk["chunk_id"],
                    "evidence_ids": [],
                    "matched_source_block_ids": [],
                    "evidence_coverage": {},
                    "proposed_relevance": 1,
                })
                item["evidence_ids"].append(evidence_id)
                item["matched_source_block_ids"].extend(sorted(matched))
                item["evidence_coverage"][evidence_id] = round(coverage, 4)
                if coverage >= 0.5:
                    item["proposed_relevance"] = 2
        relevant = sorted(candidates.values(), key=lambda item: (-item["proposed_relevance"], item["chunk_id"]))
        for item in relevant:
            item["evidence_ids"] = sorted(set(item["evidence_ids"]))
            item["matched_source_block_ids"] = sorted(set(item["matched_source_block_ids"]))
            chunk = next(row for row in chunks if row["chunk_id"] == item["chunk_id"])
            queue.append({
                "strategy": strategy,
                "question_id": question["id"],
                "chunk_id": item["chunk_id"],
                "evidence_ids": "|".join(item["evidence_ids"]),
                "coverage": json.dumps(item["evidence_coverage"], ensure_ascii=False),
                "proposed_relevance": item["proposed_relevance"],
                "review_status": "pending",
                "final_relevance": "",
                "question": question["question"],
                "chunk_text": chunk["text"],
                "review_note": "",
            })
        rows.append({
            "question_id": question["id"],
            "strategy": strategy,
            "relevant_chunk_candidates": relevant,
            "mapping_status": "draft_pending_human_review",
        })
    return rows, queue


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = root / "data/evaluation/dev_v0.1"
    chunk_dir = root / "data/chunks/DOC004"
    questions = load_jsonl(dataset / "questions.draft.jsonl")
    answers = {row["question_id"]: row for row in load_jsonl(dataset / "answers.reviewed.jsonl")}
    evidence = {row["evidence_id"]: row for row in load_jsonl(dataset / "reviewed_evidence.v0.1.jsonl")}
    queue = []
    summary = {"status": "draft_pending_human_review", "strategies": {}}
    for strategy in ("fixed", "structural"):
        chunks = load_jsonl(chunk_dir / f"{strategy}_v0.1.draft.jsonl")
        rows, strategy_queue = map_strategy(questions, answers, evidence, chunks, strategy)
        queue.extend(strategy_queue)
        output = dataset / f"gold_chunk_candidates.{strategy}.draft.jsonl"
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        summary["strategies"][strategy] = {
            "questions": len(rows),
            "candidate_pairs": len(strategy_queue),
            "questions_without_candidates": [row["question_id"] for row in rows if not row["relevant_chunk_candidates"]],
        }
    queue_path = dataset / "gold_chunk_review_queue.csv"
    with queue_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(queue[0]))
        writer.writeheader()
        writer.writerows(queue)
    (dataset / "gold_chunk_mapping_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

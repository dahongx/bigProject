#!/usr/bin/env python3
"""Validate question, reviewed answer, and reviewed evidence relationships."""

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
    questions = load_jsonl(dataset / "questions.draft.jsonl")
    answers = load_jsonl(dataset / "answers.reviewed.jsonl")
    evidence = load_jsonl(dataset / "reviewed_evidence.v0.1.jsonl")
    retrieval_labels = load_jsonl(dataset / "retrieval_eval.reviewed.jsonl")
    cited_answers = load_jsonl(dataset / "answers.with_citations.jsonl")
    blocks = load_jsonl(root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")

    question_ids = [row["id"] for row in questions]
    answer_ids = [row["question_id"] for row in answers]
    evidence_ids = [row["evidence_id"] for row in evidence]
    block_ids = {row["block_id"] for row in blocks}
    referenced_evidence = [item for row in answers for item in row["evidence_ids"]]
    referenced_blocks = [item for row in evidence for item in row["source_block_ids"]]
    retrieval_question_ids = [row["question_id"] for row in retrieval_labels]
    retrieval_evidence_ids = [
        item["evidence_id"] for row in retrieval_labels for item in row["relevant_evidence"]
    ]
    cited_answer_ids = [row["question_id"] for row in cited_answers]

    report = {
        "status": "pass",
        "counts": {"questions": len(questions), "answers": len(answers), "cited_answers": len(cited_answers), "evidence_records": len(evidence), "retrieval_labels": len(retrieval_labels)},
        "duplicate_question_ids": duplicates(question_ids),
        "duplicate_answer_question_ids": duplicates(answer_ids),
        "duplicate_evidence_ids": duplicates(evidence_ids),
        "questions_without_answers": sorted(set(question_ids) - set(answer_ids)),
        "answers_without_questions": sorted(set(answer_ids) - set(question_ids)),
        "missing_evidence_ids": sorted(set(referenced_evidence) - set(evidence_ids)),
        "unreferenced_evidence_ids": sorted(set(evidence_ids) - set(referenced_evidence)),
        "missing_source_block_ids": sorted(set(referenced_blocks) - block_ids),
        "questions_without_retrieval_labels": sorted(set(question_ids) - set(retrieval_question_ids)),
        "retrieval_labels_without_questions": sorted(set(retrieval_question_ids) - set(question_ids)),
        "duplicate_retrieval_question_ids": duplicates(retrieval_question_ids),
        "missing_retrieval_evidence_ids": sorted(set(retrieval_evidence_ids) - set(evidence_ids)),
        "answer_label_disagreements": sorted(
            question_id
            for question_id in set(answer_ids) & set(retrieval_question_ids)
            if set(next(row["evidence_ids"] for row in answers if row["question_id"] == question_id))
            != set(
                item["evidence_id"]
                for item in next(row["relevant_evidence"] for row in retrieval_labels if row["question_id"] == question_id)
            )
        ),
        "answers_without_cited_view": sorted(set(answer_ids) - set(cited_answer_ids)),
        "cited_view_without_answers": sorted(set(cited_answer_ids) - set(answer_ids)),
        "duplicate_cited_answer_ids": duplicates(cited_answer_ids),
        "invalid_expanded_citations": sorted(
            row["question_id"]
            for row in cited_answers
            if row["evidence_ids"] != [item["evidence_id"] for item in row["evidence"]]
            or any(item["review_status"] != "reviewed" for item in row["evidence"])
        ),
        "non_reviewed_answers": sorted(row["question_id"] for row in answers if row["annotation_status"] != "reviewed"),
        "non_reviewed_evidence": sorted(row["evidence_id"] for row in evidence if row["review_status"] != "reviewed"),
    }
    for key, value in report.items():
        if key not in {"status", "counts"} and value:
            report["status"] = "fail"
    output = dataset / "validation_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

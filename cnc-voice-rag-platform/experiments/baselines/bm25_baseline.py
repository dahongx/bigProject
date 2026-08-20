"""Reproducible dependency-free BM25 baseline for the CNC RAG project."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


LATIN_TOKEN_RE = re.compile(r"[a-z]+\d*(?:\.\d+)?|\d+(?:\.\d+)?", re.I)
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Keep CNC codes whole and use deterministic Chinese uni/bi-grams."""

    normalized = text.lower().replace("０", "0").replace("１", "1")
    tokens = LATIN_TOKEN_RE.findall(normalized)
    for span in CHINESE_RE.findall(normalized):
        tokens.extend(span)
        tokens.extend(span[index : index + 2] for index in range(len(span) - 1))
    return tokens


class BM25Baseline:
    def __init__(self, corpus: list[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75):
        if not corpus:
            raise ValueError("corpus must not be empty")
        self.corpus = corpus
        self.doc_ids = [str(doc.get("id", doc.get("evidence_id", doc.get("chunk_id")))) for doc in corpus]
        if any(doc_id == "None" for doc_id in self.doc_ids):
            raise ValueError("each corpus record needs id or evidence_id")
        self.k1 = k1
        self.b = b
        self.tokenized = [tokenize(str(doc["text"])) for doc in corpus]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokenized]
        self.doc_lengths = [len(tokens) for tokens in self.tokenized]
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)
        document_frequency = Counter(token for tokens in self.tokenized for token in set(tokens))
        count = len(corpus)
        self.idf = {
            token: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        query_terms = Counter(tokenize(query))
        scores = []
        for index, frequencies in enumerate(self.term_frequencies):
            length_norm = 1.0 - self.b + self.b * self.doc_lengths[index] / self.avg_doc_length
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                score += query_frequency * self.idf.get(term, 0.0) * (
                    frequency * (self.k1 + 1.0) / (frequency + self.k1 * length_norm)
                )
            scores.append(score)
        ranked = sorted(range(len(scores)), key=lambda index: (-scores[index], self.doc_ids[index]))
        return [
            {
                "id": self.doc_ids[index],
                "text": self.corpus[index]["text"],
                "score": round(scores[index], 8),
                "citation": self.corpus[index].get("citation"),
                "review_status": self.corpus[index].get("review_status"),
                "strategy": self.corpus[index].get("strategy"),
            }
            for index in ranked[:top_k]
        ]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    dataset = root / "data/evaluation/dev_v0.1"
    parser = argparse.ArgumentParser(description="Run the BM25 smoke baseline")
    parser.add_argument("--corpus", type=Path, default=dataset / "reviewed_evidence.v0.1.jsonl")
    parser.add_argument("--questions", type=Path, default=dataset / "questions.draft.jsonl")
    parser.add_argument("--answers", type=Path, default=dataset / "answers.reviewed.jsonl")
    parser.add_argument("--relevance", type=Path, default=dataset / "retrieval_eval.reviewed.jsonl")
    parser.add_argument("--output", type=Path, default=root / "experiments/results/bm25_dev_v0.1_smoke.json")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--experiment-id", default="BM25_DEV_V0.1_SMOKE")
    parser.add_argument("--experiment-kind", default="engineering_smoke_test_not_thesis_result")
    parser.add_argument("--k1", type=float, default=1.5)
    parser.add_argument("--b", type=float, default=0.75)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("top-k must be positive")
    raw_corpus = load_jsonl(args.corpus)
    corpus = [{**row, "text": row[args.text_field]} for row in raw_corpus]
    questions = load_jsonl(args.questions)
    answers = {row["question_id"]: row for row in load_jsonl(args.answers)}
    relevance = {row["question_id"]: row for row in load_jsonl(args.relevance)}
    baseline = BM25Baseline(corpus, k1=args.k1, b=args.b)

    records = []
    for question in questions:
        answer = answers[question["id"]]
        label = relevance[question["id"]]
        if "relevant_evidence" in label:
            judgments = [
                {"id": item["evidence_id"], "relevance": item["relevance"]}
                for item in label["relevant_evidence"]
            ]
        else:
            judgments = [
                {"id": item["chunk_id"], "relevance": item["proposed_relevance"]}
                for item in label["relevant_chunk_candidates"]
            ]
        relevant_ids = [item["id"] for item in judgments]
        results = baseline.search(question["question"], top_k=min(args.top_k, len(corpus)))
        records.append({
            "question_id": question["id"],
            "question": question["question"],
            "relevant_ids": relevant_ids,
            "relevance": {item["id"]: item["relevance"] for item in judgments},
            "retrieved_ids": [item["id"] for item in results],
            "results": [{"rank": rank, **item} for rank, item in enumerate(results, 1)],
        })

    service_root = Path(__file__).resolve().parents[2] / "services/cnc-rag"
    sys.path.insert(0, str(service_root))
    from evaluation.retrieval_metrics import evaluate_retrieval

    metrics = evaluate_retrieval(records, k_values=(1, 3, 5, 10))
    report = {
        "experiment_id": args.experiment_id,
        "experiment_kind": args.experiment_kind,
        "corpus": str(args.corpus),
        "questions": str(args.questions),
        "answers": str(args.answers),
        "relevance": str(args.relevance),
        "configuration": {"tokenizer": "latin_tokens_plus_chinese_unigram_bigram", "text_field": args.text_field, "k1": args.k1, "b": args.b, "top_k": args.top_k},
        "dataset_counts": {"documents": len(corpus), "questions": len(questions)},
        "metrics": metrics,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Dependency-free retrieval metrics for repeatable RAG experiments."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _validate_k(k: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def recall_at_k(relevant_ids: Iterable[str], ranked_ids: Sequence[str], k: int) -> float:
    """Return the fraction of relevant evidence IDs present in the top-k."""

    _validate_k(k)
    relevant = set(_unique(relevant_ids))
    if not relevant:
        return 0.0
    retrieved = set(_unique(ranked_ids[:k]))
    return len(relevant & retrieved) / len(relevant)


def hit_at_k(relevant_ids: Iterable[str], ranked_ids: Sequence[str], k: int) -> float:
    """Return 1 when any relevant evidence ID occurs in the top-k, else 0."""

    _validate_k(k)
    relevant = set(_unique(relevant_ids))
    if not relevant:
        return 0.0
    return float(any(item in relevant for item in _unique(ranked_ids[:k])))


def reciprocal_rank(relevant_ids: Iterable[str], ranked_ids: Sequence[str]) -> float:
    """Return the reciprocal rank of the first relevant result."""

    relevant = set(_unique(relevant_ids))
    if not relevant:
        return 0.0
    for rank, item in enumerate(_unique(ranked_ids), start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(relevance: Mapping[str, float] | Iterable[str], ranked_ids: Sequence[str], k: int) -> float:
    """Compute nDCG@k using graded or binary relevance labels."""

    _validate_k(k)
    if isinstance(relevance, Mapping):
        grades = {str(key): float(value) for key, value in relevance.items()}
    else:
        grades = {item: 1.0 for item in _unique(relevance)}

    if not grades or max(grades.values(), default=0.0) <= 0:
        return 0.0

    ranked = _unique(ranked_ids)[:k]
    dcg = sum(
        (2.0 ** grades.get(item, 0.0) - 1.0) / math.log2(rank + 1)
        for rank, item in enumerate(ranked, start=1)
    )
    ideal_grades = sorted(grades.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2.0 ** grade - 1.0) / math.log2(rank + 1)
        for rank, grade in enumerate(ideal_grades, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def evaluate_retrieval(
    records: Iterable[Mapping[str, Any]],
    *,
    k_values: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, float | int]:
    """Macro-average retrieval metrics over query records.

    Each record must contain ``relevant_ids`` and ``retrieved_ids``. Records
    without relevant evidence are counted in ``unanswerable_queries`` but are
    excluded from retrieval averages; refusal behavior is evaluated separately.
    """

    ks = tuple(dict.fromkeys(k_values))
    for k in ks:
        _validate_k(k)

    answerable: list[Mapping[str, Any]] = []
    unanswerable = 0
    for record in records:
        relevant = record.get("relevant_ids", [])
        if relevant:
            answerable.append(record)
        else:
            unanswerable += 1

    result: dict[str, float | int] = {
        "answerable_queries": len(answerable),
        "unanswerable_queries": unanswerable,
        "mrr": 0.0,
    }
    for k in ks:
        result[f"recall@{k}"] = 0.0
        result[f"hit@{k}"] = 0.0
        result[f"ndcg@{k}"] = 0.0

    if not answerable:
        return result

    result["mrr"] = sum(
        reciprocal_rank(record["relevant_ids"], record.get("retrieved_ids", []))
        for record in answerable
    ) / len(answerable)

    for k in ks:
        result[f"recall@{k}"] = sum(
            recall_at_k(record["relevant_ids"], record.get("retrieved_ids", []), k)
            for record in answerable
        ) / len(answerable)
        result[f"hit@{k}"] = sum(
            hit_at_k(record["relevant_ids"], record.get("retrieved_ids", []), k)
            for record in answerable
        ) / len(answerable)
        result[f"ndcg@{k}"] = sum(
            ndcg_at_k(
                record.get("relevance", record["relevant_ids"]),
                record.get("retrieved_ids", []),
                k,
            )
            for record in answerable
        ) / len(answerable)

    return result


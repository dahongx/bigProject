"""Evaluation utilities for the CNC-RAG research pipeline."""

from .jsonl_io import JsonlFormatError, load_jsonl, write_jsonl
from .retrieval_metrics import evaluate_retrieval, hit_at_k, ndcg_at_k, recall_at_k, reciprocal_rank

__all__ = [
    "JsonlFormatError",
    "evaluate_retrieval",
    "hit_at_k",
    "load_jsonl",
    "ndcg_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "write_jsonl",
]


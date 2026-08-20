#!/usr/bin/env python3
"""Validate chunk-matrix hashes, provenance, citations, and gold coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tokenizers import Tokenizer


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def duplicates(values: list[str]) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate token-based chunk experiment assets")
    parser.add_argument("--chunk-dir", type=Path, default=root / "data/chunks/DOC004/v0.2-draft")
    parser.add_argument("--mapping-dir", type=Path, default=root / "data/evaluation/dev_v0.1/chunk_matrix_v0.2")
    parser.add_argument("--blocks", type=Path, default=root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")
    parser.add_argument("--output", type=Path, default=root / "data/evaluation/dev_v0.1/chunk_matrix_v0.2/validation_report.json")
    args = parser.parse_args()
    manifest = json.loads((args.chunk_dir / "manifest.json").read_text(encoding="utf-8"))
    tokenizer_path = Path(manifest["tokenizer"]["file"])
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    source_blocks = {row["block_id"]: row for row in load_jsonl(args.blocks)}
    report: dict[str, Any] = {"status": "pass", "profiles": {}}
    source_hash_matches = sha256(args.blocks) == manifest["source"]["sha256"]
    tokenizer_hash_matches = sha256(tokenizer_path) == manifest["tokenizer"]["sha256"]
    if not source_hash_matches or not tokenizer_hash_matches:
        report["status"] = "fail"
    report["source_hash_matches"] = source_hash_matches
    report["tokenizer_hash_matches"] = tokenizer_hash_matches

    for profile, profile_data in manifest["profiles"].items():
        chunk_path = args.chunk_dir / profile_data["file"]
        chunks = load_jsonl(chunk_path)
        mappings = load_jsonl(args.mapping_dir / f"gold_candidates.{profile}.jsonl")
        ids = [row["chunk_id"] for row in chunks]
        invalid_token_counts = []
        invalid_citations = []
        invalid_fragments = []
        for row in chunks:
            actual_tokens = len(tokenizer.encode(row["text"], add_special_tokens=False).ids)
            if actual_tokens != row["token_count"]:
                invalid_token_counts.append(row["chunk_id"])
            if (
                row["citation"]["quote"] != row["text"]
                or row["citation"]["source_block_ids"] != row["source_block_ids"]
                or row["citation"]["pdf_pages"] != row["pdf_pages"]
            ):
                invalid_citations.append(row["chunk_id"])
            for fragment in row["source_fragments"]:
                source = source_blocks.get(fragment["block_id"])
                if source is None:
                    invalid_fragments.append(f'{row["chunk_id"]}:{fragment["block_id"]}:missing')
                    continue
                expected = (fragment["block_character_end"] - fragment["block_character_start"]) / max(
                    1, fragment["block_character_count"]
                )
                if (
                    fragment["block_character_count"] != len(source["text"].strip())
                    or not 0 <= fragment["block_character_start"] < fragment["block_character_end"] <= fragment["block_character_count"]
                    or abs(expected - fragment["coverage"]) > 1e-5
                ):
                    invalid_fragments.append(f'{row["chunk_id"]}:{fragment["block_id"]}:invalid')
        missing_candidates = [row["question_id"] for row in mappings if not row["relevant_chunk_candidates"]]
        item = {
            "chunk_count": len(chunks),
            "mapping_count": len(mappings),
            "file_hash_matches": sha256(chunk_path) == profile_data["sha256"],
            "duplicate_chunk_ids": duplicates(ids),
            "empty_chunks": [row["chunk_id"] for row in chunks if not row["text"].strip()],
            "invalid_token_counts": invalid_token_counts,
            "invalid_citations": invalid_citations,
            "invalid_source_fragments": invalid_fragments,
            "questions_without_candidates": missing_candidates,
        }
        report["profiles"][profile] = item
        if not item["file_hash_matches"] or any(
            item[key] for key in (
                "duplicate_chunk_ids", "empty_chunks", "invalid_token_counts", "invalid_citations",
                "invalid_source_fragments", "questions_without_candidates"
            )
        ):
            report["status"] = "fail"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

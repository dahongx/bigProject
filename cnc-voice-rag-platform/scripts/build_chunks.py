#!/usr/bin/env python3
"""Build fixed-window and structure-aware draft chunks with full provenance."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


SKIP_TYPES = {"header_footer"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def citation(blocks: list[dict[str, Any]], text: str) -> dict[str, Any]:
    return {
        "document_id": blocks[0]["document_id"],
        "document_title": "FANUC数控编程手册",
        "pdf_pages": sorted({block["pdf_page"] for block in blocks}),
        "printed_pages": sorted({block["printed_page"] for block in blocks}),
        "title_paths": list(dict.fromkeys(" > ".join(block["title_path"]) for block in blocks)),
        "source_block_ids": [block["block_id"] for block in blocks],
        "quote": text,
    }


def make_chunk(strategy: str, sequence: int, blocks: list[dict[str, Any]], text: str) -> dict[str, Any]:
    prefix = "DOC004_FIXED_V01" if strategy == "fixed" else "DOC004_STRUCT_V01"
    issues = sorted({issue for block in blocks for issue in block.get("issues", [])})
    title_paths = list(dict.fromkeys(" > ".join(block["title_path"]) for block in blocks))
    return {
        "chunk_id": f"{prefix}_C{sequence:04d}",
        "document_id": "DOC004",
        "strategy": strategy,
        "version": "0.1-draft",
        "text": text.strip(),
        "retrieval_text": (title_paths[0] + "\n" + text.strip()) if title_paths else text.strip(),
        "character_count": len(text.strip()),
        "source_block_ids": [block["block_id"] for block in blocks],
        "source_line_ids": list(dict.fromkeys(line_id for block in blocks for line_id in block["source_line_ids"])),
        "pdf_pages": sorted({block["pdf_page"] for block in blocks}),
        "printed_pages": sorted({block["printed_page"] for block in blocks}),
        "title_paths": title_paths,
        "block_types": list(dict.fromkeys(block["block_type"] for block in blocks)),
        "issues": issues,
        "review_status": "draft_contains_auto_ocr",
        "citation": citation(blocks, text.strip()),
    }


def build_fixed(blocks: list[dict[str, Any]], size: int, overlap: int) -> list[dict[str, Any]]:
    """Use character windows while retaining all overlapping source blocks."""
    groups = [[block for block in blocks if 111 <= block["pdf_page"] <= 128],
              [block for block in blocks if 145 <= block["pdf_page"] <= 153]]
    chunks = []
    sequence = 1
    for group in groups:
        units = [block for block in group if block["block_type"] not in SKIP_TYPES and block["text"].strip()]
        text_parts, spans, cursor = [], [], 0
        for block in units:
            value = block["text"].strip() + "\n"
            text_parts.append(value)
            spans.append((cursor, cursor + len(value), block))
            cursor += len(value)
        document_text = "".join(text_parts)
        start = 0
        while start < len(document_text):
            end = min(start + size, len(document_text))
            window = document_text[start:end].strip()
            source_blocks = [block for left, right, block in spans if left < end and right > start]
            if window and source_blocks:
                chunks.append(make_chunk("fixed", sequence, source_blocks, window))
                sequence += 1
            if end == len(document_text):
                break
            start = end - overlap
    return chunks


def build_structural(blocks: list[dict[str, Any]], max_chars: int, min_chars: int = 80) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        groups.append(current)
        current = []

    for block in blocks:
        if block["block_type"] in SKIP_TYPES or not block["text"].strip():
            continue
        new_boundary = bool(current) and (
            block["title_path"] != current[-1]["title_path"]
            or block["block_type"] in {"heading", "subheading", "exercise_heading"}
            or current[-1].get("layout_region") != block.get("layout_region")
        )
        projected = sum(len(item["text"]) + 1 for item in current) + len(block["text"])
        if new_boundary or (current and projected > max_chars):
            flush()
        current.append(block)
    flush()
    consolidated: list[list[dict[str, Any]]] = []
    for index, group in enumerate(groups):
        length = sum(len(block["text"].strip()) + 1 for block in group)
        if length < min_chars and index + 1 < len(groups):
            groups[index + 1] = group + groups[index + 1]
            continue
        if length < min_chars and consolidated:
            previous_length = sum(len(block["text"].strip()) + 1 for block in consolidated[-1])
            if previous_length + length <= max_chars:
                consolidated[-1].extend(group)
                continue
        consolidated.append(group)
    chunks = []
    for sequence, group in enumerate(consolidated, 1):
        text = "\n".join(block["text"].strip() for block in group)
        chunks.append(make_chunk("structural", sequence, group, text))
    return chunks


def report_for(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chunk_count": len(chunks),
        "average_characters": round(sum(row["character_count"] for row in chunks) / len(chunks), 2),
        "minimum_characters": min(row["character_count"] for row in chunks),
        "maximum_characters": max(row["character_count"] for row in chunks),
        "chunks_with_issues": sum(bool(row["issues"]) for row in chunks),
        "page_coverage": sorted({page for row in chunks for page in row["pdf_pages"]}),
        "block_type_counts": dict(sorted(Counter(kind for row in chunks for kind in row["block_types"]).items())),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=Path, default=root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")
    parser.add_argument("--output-dir", type=Path, default=root / "data/chunks/DOC004")
    parser.add_argument("--fixed-size", type=int, default=350)
    parser.add_argument("--fixed-overlap", type=int, default=70)
    parser.add_argument("--structural-max", type=int, default=600)
    args = parser.parse_args()
    if args.fixed_size <= 0 or not 0 <= args.fixed_overlap < args.fixed_size or args.structural_max <= 0:
        raise ValueError("invalid chunk size or overlap")
    blocks = load_jsonl(args.blocks)
    fixed = build_fixed(blocks, args.fixed_size, args.fixed_overlap)
    structural = build_structural(blocks, args.structural_max)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "fixed": args.output_dir / "fixed_v0.1.draft.jsonl",
        "structural": args.output_dir / "structural_v0.1.draft.jsonl",
    }
    for strategy, rows in (("fixed", fixed), ("structural", structural)):
        outputs[strategy].write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {
        "status": "draft_not_for_final_thesis_experiment",
        "source": str(args.blocks),
        "configuration": {"fixed_size": args.fixed_size, "fixed_overlap": args.fixed_overlap, "structural_max": args.structural_max},
        "strategies": {"fixed": report_for(fixed), "structural": report_for(structural)},
    }
    (args.output_dir / "chunk_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

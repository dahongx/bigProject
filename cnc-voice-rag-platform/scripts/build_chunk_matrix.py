#!/usr/bin/env python3
"""Build a token-based chunk experiment matrix with block-level provenance.

This script does not replace the legacy 350-character smoke artifacts. It creates
an isolated v0.2 draft matrix so character and token units cannot be confused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from tokenizers import Tokenizer


SKIP_TYPES = {"header_footer"}
DEFAULT_FIXED_PROFILES = ((256, 51), (512, 102), (1024, 205))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_page_ranges(value: str) -> list[tuple[int, int]]:
    ranges = []
    for item in value.split(","):
        left, separator, right = item.strip().partition("-")
        start, end = int(left), int(right if separator else left)
        if start <= 0 or end < start:
            raise ValueError(f"invalid page range: {item}")
        ranges.append((start, end))
    return ranges


def selected(page: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(start <= page <= end for start, end in ranges)


def token_offsets(tokenizer: Tokenizer, text: str) -> list[tuple[int, int]]:
    return [(start, end) for start, end in tokenizer.encode(text, add_special_tokens=False).offsets if end > start]


def token_count(tokenizer: Tokenizer, text: str) -> int:
    return len(token_offsets(tokenizer, text))


def title_paths(blocks: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(" > ".join(block["title_path"]) for block in blocks if block.get("title_path")))


def fragments_for_window(
    spans: list[tuple[int, int, dict[str, Any]]], start: int, end: int
) -> list[dict[str, Any]]:
    fragments = []
    for left, right, block in spans:
        intersection_start, intersection_end = max(left, start), min(right, end)
        if intersection_start >= intersection_end:
            continue
        block_text = block["text"].strip()
        local_start = max(0, intersection_start - left)
        local_end = min(len(block_text), intersection_end - left)
        if local_start >= local_end:
            continue
        fragments.append({
            "block_id": block["block_id"],
            "block_character_start": local_start,
            "block_character_end": local_end,
            "block_character_count": len(block_text),
            "coverage": round((local_end - local_start) / max(1, len(block_text)), 6),
        })
    return fragments


def whole_fragments(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "block_id": block["block_id"],
        "block_character_start": 0,
        "block_character_end": len(block["text"].strip()),
        "block_character_count": len(block["text"].strip()),
        "coverage": 1.0,
    } for block in blocks]


def make_chunk(
    *,
    tokenizer: Tokenizer,
    profile: str,
    sequence: int,
    blocks: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    text: str,
    target_tokens: int,
    overlap_tokens: int,
) -> dict[str, Any]:
    clean_text = text.strip()
    paths = title_paths(blocks)
    retrieval_text = (paths[0] + "\n" + clean_text) if paths else clean_text
    prefix = profile.upper().replace("-", "_")
    source_block_ids = [fragment["block_id"] for fragment in fragments]
    issues = sorted({issue for block in blocks for issue in block.get("issues", [])})
    pages = sorted({block["pdf_page"] for block in blocks})
    printed_pages = sorted({block["printed_page"] for block in blocks})
    citation = {
        "document_id": blocks[0]["document_id"],
        "document_title": "FANUC数控编程手册",
        "pdf_pages": pages,
        "printed_pages": printed_pages,
        "title_paths": paths,
        "source_block_ids": source_block_ids,
        "quote": clean_text,
    }
    return {
        "chunk_id": f"DOC004_{prefix}_V02_C{sequence:04d}",
        "document_id": "DOC004",
        "strategy": "structural_token" if profile.startswith("structural") else "fixed_token",
        "profile": profile,
        "version": "0.2-draft",
        "text": clean_text,
        "retrieval_text": retrieval_text,
        "character_count": len(clean_text),
        "token_count": token_count(tokenizer, clean_text),
        "retrieval_token_count": token_count(tokenizer, retrieval_text),
        "target_tokens": target_tokens,
        "overlap_tokens": overlap_tokens,
        "source_block_ids": source_block_ids,
        "source_fragments": fragments,
        "source_line_ids": list(dict.fromkeys(line_id for block in blocks for line_id in block["source_line_ids"])),
        "pdf_pages": pages,
        "printed_pages": printed_pages,
        "title_paths": paths,
        "block_types": list(dict.fromkeys(block["block_type"] for block in blocks)),
        "issues": issues,
        "review_status": "draft_contains_auto_ocr",
        "citation": citation,
    }


def document_groups(blocks: list[dict[str, Any]], ranges: list[tuple[int, int]]) -> list[list[dict[str, Any]]]:
    groups = []
    for start, end in ranges:
        group = [
            block for block in blocks
            if start <= block["pdf_page"] <= end
            and block["block_type"] not in SKIP_TYPES
            and block["text"].strip()
        ]
        if group:
            groups.append(group)
    return groups


def build_fixed(
    tokenizer: Tokenizer,
    blocks: list[dict[str, Any]],
    ranges: list[tuple[int, int]],
    size: int,
    overlap: int,
) -> list[dict[str, Any]]:
    profile = f"fixed_t{size}_o{overlap}"
    chunks, sequence = [], 1
    for group in document_groups(blocks, ranges):
        text_parts: list[str] = []
        spans: list[tuple[int, int, dict[str, Any]]] = []
        cursor = 0
        for block in group:
            block_text = block["text"].strip()
            text_parts.append(block_text + "\n")
            spans.append((cursor, cursor + len(block_text), block))
            cursor += len(block_text) + 1
        document_text = "".join(text_parts)
        offsets = token_offsets(tokenizer, document_text)
        step = size - overlap
        for token_start in range(0, len(offsets), step):
            token_end = min(token_start + size, len(offsets))
            char_start, char_end = offsets[token_start][0], offsets[token_end - 1][1]
            # SentencePiece tokenization can gain one boundary token when a slice is
            # encoded without its original left context. Shrink the right edge until
            # the independently encoded chunk obeys the advertised target exactly.
            while token_end > token_start + 1 and token_count(
                tokenizer, document_text[char_start:char_end]
            ) > size:
                token_end -= 1
                char_end = offsets[token_end - 1][1]
            fragments = fragments_for_window(spans, char_start, char_end)
            source_ids = {fragment["block_id"] for fragment in fragments}
            source_blocks = [block for block in group if block["block_id"] in source_ids]
            chunks.append(make_chunk(
                tokenizer=tokenizer,
                profile=profile,
                sequence=sequence,
                blocks=source_blocks,
                fragments=fragments,
                text=document_text[char_start:char_end],
                target_tokens=size,
                overlap_tokens=overlap,
            ))
            sequence += 1
            if token_end == len(offsets):
                break
    return chunks


def build_structural(
    tokenizer: Tokenizer,
    blocks: list[dict[str, Any]],
    ranges: list[tuple[int, int]],
    max_tokens: int,
    min_tokens: int,
) -> list[dict[str, Any]]:
    profile = f"structural_t{max_tokens}"
    raw_groups: list[list[dict[str, Any]]] = []
    for document_group in document_groups(blocks, ranges):
        current: list[dict[str, Any]] = []
        for block in document_group:
            candidate = current + [block]
            candidate_text = "\n".join(item["text"].strip() for item in candidate)
            boundary = bool(current) and (
                block["title_path"] != current[-1]["title_path"]
                or block["block_type"] in {"heading", "subheading", "exercise_heading"}
                or current[-1].get("layout_region") != block.get("layout_region")
            )
            if current and (boundary or token_count(tokenizer, candidate_text) > max_tokens):
                raw_groups.append(current)
                current = []
            current.append(block)
        if current:
            raw_groups.append(current)

    consolidated: list[list[dict[str, Any]]] = []
    for group in raw_groups:
        group_text = "\n".join(block["text"].strip() for block in group)
        if consolidated and token_count(tokenizer, group_text) < min_tokens:
            previous = consolidated[-1]
            combined = previous + group
            combined_text = "\n".join(block["text"].strip() for block in combined)
            same_section = previous[-1]["title_path"] == group[0]["title_path"]
            heading_bridge = all(block["block_type"] in {"heading", "subheading", "exercise_heading"} for block in group)
            if (same_section or heading_bridge) and token_count(tokenizer, combined_text) <= max_tokens:
                previous.extend(group)
                continue
        consolidated.append(group)

    chunks = []
    for sequence, group in enumerate(consolidated, 1):
        text = "\n".join(block["text"].strip() for block in group)
        chunks.append(make_chunk(
            tokenizer=tokenizer,
            profile=profile,
            sequence=sequence,
            blocks=group,
            fragments=whole_fragments(group),
            text=text,
            target_tokens=max_tokens,
            overlap_tokens=0,
        ))
    return chunks


def profile_report(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chunk_count": len(chunks),
        "average_tokens": round(sum(row["token_count"] for row in chunks) / len(chunks), 2),
        "minimum_tokens": min(row["token_count"] for row in chunks),
        "maximum_tokens": max(row["token_count"] for row in chunks),
        "average_characters": round(sum(row["character_count"] for row in chunks) / len(chunks), 2),
        "chunks_with_ocr_issues": sum(bool(row["issues"]) for row in chunks),
        "chunks_over_target": [row["chunk_id"] for row in chunks if row["token_count"] > row["target_tokens"]],
        "page_coverage": sorted({page for row in chunks for page in row["pdf_pages"]}),
        "block_type_counts": dict(sorted(Counter(kind for row in chunks for kind in row["block_types"]).items())),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build token-based fixed and structural chunk profiles")
    parser.add_argument("--blocks", type=Path, default=root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")
    parser.add_argument("--tokenizer", type=Path, default=root / "models/bge-m3-tokenizer/tokenizer.json")
    parser.add_argument("--output-dir", type=Path, default=root / "data/chunks/DOC004/v0.2-draft")
    parser.add_argument("--page-ranges", default="111-128,145-153")
    parser.add_argument("--structural-max", type=int, default=512)
    parser.add_argument("--structural-min", type=int, default=64)
    args = parser.parse_args()
    if not args.blocks.is_file() or not args.tokenizer.is_file():
        raise FileNotFoundError("blocks or tokenizer file is missing")
    ranges = parse_page_ranges(args.page_ranges)
    blocks = load_jsonl(args.blocks)
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    profiles: dict[str, list[dict[str, Any]]] = {}
    for size, overlap in DEFAULT_FIXED_PROFILES:
        rows = build_fixed(tokenizer, blocks, ranges, size, overlap)
        profiles[f"fixed_t{size}_o{overlap}"] = rows
    structural = build_structural(tokenizer, blocks, ranges, args.structural_max, args.structural_min)
    profiles[f"structural_t{args.structural_max}"] = structural

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_profiles = {}
    for name, rows in profiles.items():
        output = args.output_dir / f"{name}.jsonl"
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        manifest_profiles[name] = {
            "file": output.name,
            "sha256": sha256(output),
            "report": profile_report(rows),
        }
    manifest = {
        "status": "draft_not_for_final_thesis_experiment",
        "version": "0.2-draft",
        "source": {"file": str(args.blocks), "sha256": sha256(args.blocks), "page_ranges": ranges},
        "tokenizer": {
            "name": "BAAI/bge-m3",
            "file": str(args.tokenizer),
            "sha256": sha256(args.tokenizer),
            "special_tokens_excluded_from_chunk_counts": True,
        },
        "profiles": manifest_profiles,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prioritize manual review items that can change chunking or gold evidence."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


CHAPTER_RE = re.compile(r"^第(\d+)章")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_chapter(pdf_page: int) -> int | None:
    if 111 <= pdf_page <= 128:
        return 2
    if 145 <= pdf_page <= 153:
        return 3
    return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    block_path = root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl"
    evidence_path = root / "data/evaluation/dev_v0.1/reviewed_evidence.v0.1.jsonl"
    structural_path = root / "data/chunks/DOC004/v0.2-draft/structural_t512.jsonl"
    output = root / "data/parsed/DOC004/data_review_queue_v0.2.csv"
    blocks = load_jsonl(block_path)
    evidence = load_jsonl(evidence_path)
    chunks = load_jsonl(structural_path)

    evidence_by_block: dict[str, list[str]] = defaultdict(list)
    for item in evidence:
        for block_id in item["source_block_ids"]:
            evidence_by_block[block_id].append(item["evidence_id"])
    short_chunk_by_block: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        if chunk["token_count"] < 64:
            for block_id in chunk["source_block_ids"]:
                short_chunk_by_block[block_id].append(chunk["chunk_id"])

    rows = []
    for block in blocks:
        reasons = []
        expected = expected_chapter(block["pdf_page"])
        observed_chapters = {
            int(match.group(1))
            for segment in block.get("title_path", [])
            if (match := CHAPTER_RE.match(segment))
        }
        if expected is not None and observed_chapters and observed_chapters != {expected}:
            reasons.append("suspicious_chapter_path")
        if block["block_id"] in short_chunk_by_block:
            reasons.append("short_structural_chunk")
        if block.get("issues"):
            reasons.append("ocr_or_structure_issue")
        if block["block_id"] in evidence_by_block:
            reasons.append("used_by_reviewed_evidence")
        if not reasons:
            continue
        high_risk = any(reason in reasons for reason in ("suspicious_chapter_path", "short_structural_chunk", "ocr_or_structure_issue"))
        evidence_used = block["block_id"] in evidence_by_block
        priority = "P0" if high_risk and evidence_used else "P1" if high_risk or evidence_used else "P2"
        rows.append({
            "priority": priority,
            "pdf_page": block["pdf_page"],
            "printed_page": block["printed_page"],
            "block_id": block["block_id"],
            "block_type": block["block_type"],
            "reasons": "|".join(reasons),
            "issues": "|".join(block.get("issues", [])),
            "evidence_ids": "|".join(sorted(evidence_by_block.get(block["block_id"], []))),
            "short_chunk_ids": "|".join(sorted(short_chunk_by_block.get(block["block_id"], []))),
            "title_path": " > ".join(block.get("title_path", [])),
            "text": block["text"],
            "page_image": str(root / f'data/parsed/DOC004/rendered/page_{block["pdf_page"]:03d}.png'),
            "review_status": "pending",
            "corrected_text": "",
            "corrected_title_path": "",
            "review_note": "",
        })
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    rows.sort(key=lambda row: (priority_order[row["priority"]], row["pdf_page"], row["block_id"]))
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = {priority: sum(row["priority"] == priority for row in rows) for priority in ("P0", "P1", "P2")}
    print(json.dumps({"output": str(output), "items": len(rows), "priority_counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

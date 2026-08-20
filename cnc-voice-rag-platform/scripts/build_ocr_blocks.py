#!/usr/bin/env python3
"""Convert immutable PaddleOCR page output into traceable review blocks.

This stage is deliberately conservative: it never edits OCR source files and
does not silently repair domain terms, numbers, or CNC codes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


SECTION_RE = re.compile(r"^(\d+(?:\.\d+){1,2})\s*(.+)?$")
SUBHEADING_RE = re.compile(r"^（[0-9一二三四五六七八九十]+）")
CAPTION_RE = re.compile(r"^[图表]\s*\d+[-—]\d+")
PAGE_HEADER_RE = re.compile(r"^(?:第.*章.*\d{2,3}|\d{1,3}|FANUC数控编程手册)$")
CODE_TOKEN_RE = re.compile(r"(?:^|\s)(?:N\d+)?\s*(?:G\d{1,3}|M\d{1,3}|[XYZUWRIJKFPQSDT][-+]?\d)", re.I)
SUSPICIOUS_RE = re.compile(r"(?:GOO|执加|进考虑|平选择关|中轨迹|建刀具|第章|第③章)")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=root / "data/parsed/DOC004/standardization_config.json")
    parser.add_argument("--pages-dir", type=Path, default=root / "data/parsed/DOC004/pages")
    parser.add_argument("--output", type=Path, default=root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")
    parser.add_argument("--report", type=Path, default=root / "data/parsed/DOC004/block_build_report.json")
    parser.add_argument("--review-queue", type=Path, default=root / "data/parsed/DOC004/manual_review_queue.csv")
    return parser.parse_args()


def expand_page_paths(mapping: dict[str, list[str]]) -> dict[int, list[str]]:
    expanded: dict[int, list[str]] = {}
    for key, value in mapping.items():
        if "-" in key:
            start, end = (int(x) for x in key.split("-", 1))
            for page in range(start, end + 1):
                expanded[page] = value
        else:
            expanded[int(key)] = value
    return expanded


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_code(text: str) -> bool:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    return bool(CODE_TOKEN_RE.search(text)) and chinese <= 4


def classify(text: str, line_index: int) -> str:
    if line_index <= 2 and PAGE_HEADER_RE.match(text):
        return "header_footer"
    if SECTION_RE.match(text):
        return "heading"
    if SUBHEADING_RE.match(text):
        return "subheading"
    if CAPTION_RE.match(text) and not re.match(r"^图\s*\d+[-—]\d+所示", text):
        return "caption"
    if text == "练一练":
        return "exercise_heading"
    if text in {"指令格式：", "各地址含义：", "注意："}:
        return "label"
    if is_code(text):
        return "code"
    return "paragraph"


def update_title_path(path: list[str], heading: str, chapter_titles: dict[str, str]) -> list[str]:
    match = SECTION_RE.match(heading)
    if not match:
        return path
    number = match.group(1)
    level = number.count(".") + 1
    chapter = number.split(".")[0]
    chapter_title = chapter_titles.get(chapter, f"第{chapter}章")
    if level == 2:
        return [chapter_title, heading]
    parent_number = ".".join(number.split(".")[:-1])
    parent = next((item for item in path if item.startswith(parent_number + " ")), parent_number)
    return [chapter_title, parent, heading]


def page_lines(page_data: dict[str, Any]) -> list[dict[str, Any]]:
    result = page_data["results"][0]
    texts = result["rec_texts"]
    scores = result["rec_scores"]
    boxes = result["rec_boxes"]
    assert len(texts) == len(scores) == len(boxes), "OCR arrays differ in length"
    rows = []
    for index, (text, score, box) in enumerate(zip(texts, scores, boxes), 1):
        clean = normalize(text)
        if not clean:
            continue
        rows.append({
            "line_index": index,
            "source_line_id": f'{page_data["document_id"]}_P{page_data["pdf_page"]:03d}_L{index:03d}',
            "text": clean,
            "score": float(score),
            "box": box,
            "type": classify(clean, index),
        })
    return rows


def should_merge(current: dict[str, Any], row: dict[str, Any]) -> bool:
    if current["block_type"] != "paragraph" or row["type"] != "paragraph":
        return False
    if len(current["text"]) + len(row["text"]) > 260:
        return False
    if current["text"].endswith(("。", "！", "？", "；", "：")):
        return False
    return True


def build_blocks(config: dict[str, Any], pages_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    initial_paths = expand_page_paths(config["initial_title_paths"])
    blocks: list[dict[str, Any]] = []
    source_line_ids: list[str] = []
    per_page: dict[str, Any] = {}

    for pdf_page in config["pdf_pages"]:
        page_file = pages_dir / f"page_{pdf_page:03d}_ocr.json"
        page_data = json.loads(page_file.read_text(encoding="utf-8"))
        lines = page_lines(page_data)
        table_mode = False
        table_line_count = 0
        for row in lines:
            is_table_caption = row["type"] == "caption" and row["text"].startswith("表")
            if is_table_caption:
                table_mode = True
                table_line_count = 0
            elif table_mode and row["type"] in {"heading", "subheading", "exercise_heading", "caption"}:
                table_mode = False
            elif table_mode and table_line_count >= 30:
                table_mode = False
            row["layout_region"] = "table_candidate" if table_mode else None
            if table_mode:
                table_line_count += 1
        source_line_ids.extend(row["source_line_id"] for row in lines)
        title_path = list(initial_paths[pdf_page])
        page_blocks: list[dict[str, Any]] = []

        for row in lines:
            if row["type"] == "heading":
                title_path = update_title_path(title_path, row["text"], config["chapter_titles"])
            issues = []
            if row["score"] < 0.85:
                issues.append("low_confidence")
            if SUSPICIOUS_RE.search(row["text"]):
                issues.append("possible_ocr_confusion")
            if row["type"] == "caption" and row["text"].startswith("表"):
                issues.append("table_layout_requires_review")
            elif row["layout_region"] == "table_candidate":
                issues.append("inside_table_candidate")
            if row["type"] == "header_footer" and "第章" in row["text"]:
                issues.append("header_chapter_number_missing")

            if page_blocks and should_merge(page_blocks[-1], row):
                block = page_blocks[-1]
                block["text"] += row["text"]
                block["normalized_text"] = normalize(block["text"])
                block["source_line_ids"].append(row["source_line_id"])
                block["source_boxes"].append(row["box"])
                block["source_scores"].append(round(row["score"], 6))
                block["average_confidence"] = round(mean(block["source_scores"]), 6)
                block["issues"] = sorted(set(block["issues"] + issues))
                if row["layout_region"]:
                    block["layout_region"] = row["layout_region"]
                continue

            page_blocks.append({
                "block_id": "",
                "document_id": config["document_id"],
                "batch_id": config["batch_id"],
                "pdf_page": pdf_page,
                "pdf_index": pdf_page - 1,
                "printed_page": pdf_page + config["printed_page_offset"],
                "block_type": row["type"],
                "layout_region": row["layout_region"],
                "text": row["text"],
                "normalized_text": row["text"],
                "title_path": list(title_path),
                "source_line_ids": [row["source_line_id"]],
                "source_boxes": [row["box"]],
                "source_scores": [round(row["score"], 6)],
                "average_confidence": round(row["score"], 6),
                "review_status": "auto_draft",
                "issues": issues,
            })

        for sequence, block in enumerate(page_blocks, 1):
            block["block_id"] = f'{config["document_id"]}_P{pdf_page:03d}_B{sequence:03d}'
        blocks.extend(page_blocks)
        per_page[str(pdf_page)] = {
            "ocr_lines": len(lines),
            "blocks": len(page_blocks),
            "flagged_blocks": sum(bool(block["issues"]) for block in page_blocks),
        }

    represented = [line_id for block in blocks for line_id in block["source_line_ids"]]
    block_ids = [block["block_id"] for block in blocks]
    report = {
        "document_id": config["document_id"],
        "batch_id": config["batch_id"],
        "status": "draft_requires_manual_review",
        "page_count": len(config["pdf_pages"]),
        "source_line_count": len(source_line_ids),
        "represented_source_line_count": len(represented),
        "missing_source_line_ids": sorted(set(source_line_ids) - set(represented)),
        "duplicate_source_line_ids": sorted(k for k, v in Counter(represented).items() if v > 1),
        "block_count": len(blocks),
        "duplicate_block_ids": sorted(k for k, v in Counter(block_ids).items() if v > 1),
        "block_type_counts": dict(sorted(Counter(block["block_type"] for block in blocks).items())),
        "issue_counts": dict(sorted(Counter(issue for block in blocks for issue in block["issues"]).items())),
        "per_page": per_page,
    }
    return blocks, report


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    blocks, report = build_blocks(config, args.pages_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(block, ensure_ascii=False) + "\n" for block in blocks), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    issue_priority = {"possible_ocr_confusion": 1, "table_layout_requires_review": 1,
                      "inside_table_candidate": 2, "low_confidence": 3,
                      "header_chapter_number_missing": 4}
    review_rows = []
    for block in blocks:
        if not block["issues"]:
            continue
        review_rows.append({
            "priority": min(issue_priority.get(issue, 9) for issue in block["issues"]),
            "block_id": block["block_id"],
            "pdf_page": block["pdf_page"],
            "printed_page": block["printed_page"],
            "block_type": block["block_type"],
            "issues": "|".join(block["issues"]),
            "text": block["text"],
            "review_status": "pending",
            "corrected_text": "",
            "review_note": "",
        })
    review_rows.sort(key=lambda row: (row["priority"], row["pdf_page"], row["block_id"]))
    args.review_queue.parent.mkdir(parents=True, exist_ok=True)
    with args.review_queue.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(review_rows[0]) if review_rows else ["block_id"])
        writer.writeheader()
        writer.writerows(review_rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

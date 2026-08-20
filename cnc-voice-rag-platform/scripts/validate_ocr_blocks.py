#!/usr/bin/env python3
"""Validate OCR sample integrity and batch block traceability."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


SAMPLE_EXPECTATIONS = {
    4: ["978-7-122-29046-5"],
    6: ["目录"],
    113: ["G90", "表2-30"],
    145: ["G41", "G42", "G90", "G91"],
    181: ["G80", "G81", "G83", "G84"],
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages-dir", type=Path, default=root / "data/parsed/DOC004/pages")
    parser.add_argument("--blocks", type=Path, default=root / "data/parsed/DOC004/blocks.batch_001.draft.jsonl")
    parser.add_argument("--output", type=Path, default=root / "data/parsed/DOC004/block_validation_report.json")
    args = parser.parse_args()

    checks = []
    for page, expected in SAMPLE_EXPECTATIONS.items():
        data = json.loads((args.pages_dir / f"page_{page:03d}_ocr.json").read_text(encoding="utf-8"))
        result = data["results"][0]
        text = "\n".join(result["rec_texts"])
        checks.append({
            "pdf_page": page,
            "array_lengths_equal": len(result["rec_texts"]) == len(result["rec_scores"]) == len(result["rec_boxes"]),
            "expected_tokens": expected,
            "missing_expected_tokens": [token for token in expected if token not in text],
        })

    blocks = [json.loads(line) for line in args.blocks.read_text(encoding="utf-8").splitlines() if line.strip()]
    block_ids = [block["block_id"] for block in blocks]
    source_ids = [line_id for block in blocks for line_id in block["source_line_ids"]]
    block_pages = sorted(set(block["pdf_page"] for block in blocks))
    expected_source_ids = []
    for page in block_pages:
        data = json.loads((args.pages_dir / f"page_{page:03d}_ocr.json").read_text(encoding="utf-8"))
        result = data["results"][0]
        expected_source_ids.extend(
            f'DOC004_P{page:03d}_L{index:03d}'
            for index, text in enumerate(result["rec_texts"], 1)
            if isinstance(text, str) and text.strip()
        )
    report = {
        "status": "pass" if all(check["array_lengths_equal"] and not check["missing_expected_tokens"] for check in checks) else "fail",
        "representative_page_checks": checks,
        "batch_checks": {
            "block_count": len(blocks),
            "pages": block_pages,
            "page_count": len(block_pages),
            "duplicate_block_ids": sorted(key for key, count in Counter(block_ids).items() if count > 1),
            "duplicate_source_line_ids": sorted(key for key, count in Counter(source_ids).items() if count > 1),
            "missing_source_line_ids": sorted(set(expected_source_ids) - set(source_ids)),
            "unexpected_source_line_ids": sorted(set(source_ids) - set(expected_source_ids)),
            "invalid_printed_page_mappings": [block["block_id"] for block in blocks if block["printed_page"] != block["pdf_page"] - 8],
            "empty_text_blocks": [block["block_id"] for block in blocks if not block["text"].strip()],
            "invalid_review_status": [block["block_id"] for block in blocks if block["review_status"] != "auto_draft"],
        },
    }
    if any(report["batch_checks"][key] for key in ("duplicate_block_ids", "duplicate_source_line_ids", "missing_source_line_ids", "unexpected_source_line_ids", "invalid_printed_page_mappings", "empty_text_blocks", "invalid_review_status")):
        report["status"] = "fail"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

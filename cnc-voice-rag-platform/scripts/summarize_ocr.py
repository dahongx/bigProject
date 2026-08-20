"""Summarize PaddleOCR page JSON files for reproducible batch QA."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CODE_PATTERN = re.compile(
    r"(?i)(?<![A-Z])[GMTFSXYZIJKRPQ]\s*[+-]?\d+(?:\.\d+)?"
)


def parse_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(value) for value in part.split("-", maxsplit=1))
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return list(dict.fromkeys(pages))


def summarize_page(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    texts = [
        text
        for result in data.get("results", [])
        for text in result.get("rec_texts", [])
        if isinstance(text, str) and text.strip()
    ]
    scores = [
        float(score)
        for result in data.get("results", [])
        for score in result.get("rec_scores", [])
    ]
    joined = "\n".join(texts)
    codes = sorted(set(match.group(0).replace(" ", "") for match in CODE_PATTERN.finditer(joined)))
    low_confidence = [
        {"text": text, "score": round(score, 4)}
        for text, score in zip(texts, scores)
        if score < 0.8
    ]
    return {
        "pdf_page": data["pdf_page"],
        "pdf_index": data["pdf_index"],
        "line_count": len(texts),
        "character_count": len(joined),
        "average_confidence": round(sum(scores) / len(scores), 4) if scores else None,
        "minimum_confidence": round(min(scores), 4) if scores else None,
        "elapsed_seconds": data.get("elapsed_seconds"),
        "code_count": len(codes),
        "codes": codes,
        "low_confidence_lines": low_confidence,
        "replacement_character_count": joined.count("\ufffd"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总OCR批次质量")
    parser.add_argument("--pages-dir", required=True, type=Path)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    requested_pages = parse_pages(args.pages)
    summaries = []
    missing_pages = []
    for page in requested_pages:
        path = args.pages_dir / f"page_{page:03d}_ocr.json"
        if not path.is_file():
            missing_pages.append(page)
            continue
        summaries.append(summarize_page(path))

    nonempty = [item for item in summaries if item["line_count"] > 0]
    total_seconds = sum(float(item["elapsed_seconds"] or 0) for item in summaries)
    weighted_score_sum = sum(
        item["average_confidence"] * item["line_count"]
        for item in nonempty
        if item["average_confidence"] is not None
    )
    total_lines = sum(item["line_count"] for item in nonempty)
    report = {
        "requested_pages": requested_pages,
        "completed_pages": [item["pdf_page"] for item in summaries],
        "missing_pages": missing_pages,
        "empty_pages": [item["pdf_page"] for item in summaries if item["line_count"] == 0],
        "page_count": len(summaries),
        "total_lines": total_lines,
        "total_characters": sum(item["character_count"] for item in summaries),
        "total_unique_code_mentions_by_page": sum(item["code_count"] for item in summaries),
        "weighted_average_confidence": round(weighted_score_sum / total_lines, 4)
        if total_lines
        else None,
        "total_elapsed_seconds": round(total_seconds, 3),
        "average_elapsed_seconds_per_page": round(total_seconds / len(summaries), 3)
        if summaries
        else None,
        "replacement_character_count": sum(
            item["replacement_character_count"] for item in summaries
        ),
        "pages": summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in report.items() if key != "pages"}, ensure_ascii=False, indent=2))
    return 1 if missing_pages or report["empty_pages"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

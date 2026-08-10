"""Strict JSONL helpers with an explicit legacy-import escape hatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class JsonlFormatError(ValueError):
    """Raised when a JSONL file contains a malformed or non-object row."""


def load_jsonl(
    path: str | Path,
    *,
    allow_legacy_average_footer: bool = False,
) -> list[dict[str, Any]]:
    """Load a UTF-8 JSONL file.

    The legacy FAQ evaluator appended a plain-text ``Average score:`` line to
    otherwise valid JSONL. New experiments reject that format by default. The
    compatibility flag is intended only for importing historical results.
    """

    source = Path(path)
    records: list[dict[str, Any]] = []

    with source.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if allow_legacy_average_footer and line.startswith("Average score:"):
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JsonlFormatError(
                    f"{source}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc

            if not isinstance(value, dict):
                raise JsonlFormatError(
                    f"{source}:{line_number}: expected a JSON object"
                )
            records.append(value)

    return records


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> None:
    """Write records as UTF-8 JSONL without adding a non-JSON summary footer."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(dict(record), ensure_ascii=False))
            stream.write("\n")


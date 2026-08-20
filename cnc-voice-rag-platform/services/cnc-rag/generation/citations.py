"""Build user-facing citations strictly from actually retrieved chunks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _page_label(values: Sequence[int]) -> str:
    pages = list(dict.fromkeys(int(value) for value in values))
    if not pages:
        return "页码未知"
    if len(pages) == 1:
        return f"第{pages[0]}页"
    return f"第{pages[0]}—{pages[-1]}页"


def build_user_citations(
    retrieved_results: Sequence[Mapping[str, Any]],
    *,
    cited_chunk_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return citations for retrieved chunks only.

    ``cited_chunk_ids`` may be supplied by a generation model or citation
    selector. Referencing any ID absent from the retrieval result is rejected,
    which prevents evaluation gold labels from leaking into runtime answers.
    """

    retrieved_by_id = {str(row["id"]): row for row in retrieved_results}
    selected = list(dict.fromkeys(str(value) for value in (cited_chunk_ids or retrieved_by_id)))
    missing = [chunk_id for chunk_id in selected if chunk_id not in retrieved_by_id]
    if missing:
        raise ValueError(f"citation IDs were not retrieved: {missing}")
    citations = []
    for number, chunk_id in enumerate(selected, 1):
        result = retrieved_by_id[chunk_id]
        source = result.get("citation")
        if not isinstance(source, Mapping):
            raise ValueError(f"retrieved chunk has no citation metadata: {chunk_id}")
        title_paths = list(source.get("title_paths", []))
        printed_pages = list(source.get("printed_pages", []))
        pdf_pages = list(source.get("pdf_pages", []))
        citations.append({
            "citation_number": number,
            "chunk_id": chunk_id,
            "document_id": source.get("document_id"),
            "document_title": source.get("document_title"),
            "section": title_paths[0] if title_paths else None,
            "printed_pages": printed_pages,
            "pdf_pages": pdf_pages,
            "quote": source.get("quote"),
            "retrieval_score": result.get("score"),
            "display": f'[{number}]《{source.get("document_title", "未知文档")}》{_page_label(printed_pages)}'
            + (f"，{title_paths[0]}" if title_paths else ""),
        })
    return citations


def attach_citations(
    answer: str,
    retrieved_results: Sequence[Mapping[str, Any]],
    *,
    cited_chunk_ids: Iterable[str],
) -> dict[str, Any]:
    if not answer.strip():
        raise ValueError("answer must not be empty")
    return {
        "answer": answer.strip(),
        "citations": build_user_citations(retrieved_results, cited_chunk_ids=cited_chunk_ids),
    }

"""Markdown chunking utilities for the RAG pipeline."""

from __future__ import annotations

import re

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - compatibility with newer LangChain packaging
    from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import ChunkingConfig

_HEADING_PATTERN = re.compile(r"^\s*(#{1,6})\s+(.*?)\s*$")


async def chunk_text(
    markdown_pages: dict[int, str], config: ChunkingConfig
) -> list[dict[str, object]]:
    """Split markdown into chunks while retaining page-range provenance."""
    if not markdown_pages:
        return []

    ordered_pages = sorted(markdown_pages.items())
    combined_parts: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    cursor = 0

    for index, (page_number, page_text) in enumerate(ordered_pages):
        if index:
            combined_parts.append("\n\n")
            cursor += 2

        combined_parts.append(page_text)
        start = cursor
        cursor += len(page_text)
        page_spans.append((page_number, start, cursor))

    combined_text = "".join(combined_parts)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=config.separators,
        add_start_index=True,
    )

    chunks: list[dict[str, object]] = []
    for chunk_index, document in enumerate(splitter.create_documents([combined_text])):
        chunk_text_value = document.page_content.strip()
        if not chunk_text_value:
            continue

        start_index = int(document.metadata.get("start_index", 0))
        end_index = start_index + len(document.page_content)
        page_start, page_end = _resolve_page_range(page_spans, start_index, end_index)
        heading = _extract_heading(chunk_text_value)
        chunks.append(
            {
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "text": chunk_text_value,
                "heading": heading,
                "metadata": {
                    "heading": heading,
                    "page_range": [page_start, page_end],
                },
            }
        )

    return chunks


def _resolve_page_range(
    page_spans: list[tuple[int, int, int]], start_index: int, end_index: int
) -> tuple[int, int]:
    overlapping_pages = [
        page_number
        for page_number, page_start, page_end in page_spans
        if start_index < page_end and end_index > page_start
    ]
    if overlapping_pages:
        return overlapping_pages[0], overlapping_pages[-1]

    if start_index <= page_spans[0][1]:
        return page_spans[0][0], page_spans[0][0]

    return page_spans[-1][0], page_spans[-1][0]


def _extract_heading(chunk_text_value: str) -> str | None:
    first_line = (
        chunk_text_value.splitlines()[0].strip()
        if chunk_text_value.splitlines()
        else ""
    )
    match = _HEADING_PATTERN.match(first_line)
    if match is None:
        return None
    return match.group(2).strip()

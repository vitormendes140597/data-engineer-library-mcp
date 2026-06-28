"""Markdown chunking utilities for the RAG pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - compatibility with newer LangChain packaging
    from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import ChunkingConfig
from src.extraction.models import DocumentElement, ElementType

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


@dataclass
class _ChunkDraft:
    text_parts: list[str] = field(default_factory=list)
    elements: list[DocumentElement] = field(default_factory=list)
    heading_path: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Return the draft text with element boundaries preserved."""
        return "\n\n".join(part for part in self.text_parts if part.strip()).strip()


async def chunk_elements(
    elements: list[DocumentElement],
    config: ChunkingConfig,
) -> list[dict[str, object]]:
    """Pack structured document elements into chunk payloads."""
    chunks: list[dict[str, object]] = []
    draft = _ChunkDraft()
    heading_stack: list[tuple[int, str]] = []
    previous_caption: DocumentElement | None = None

    for element in elements:
        if element.element_type == ElementType.HEADING:
            chunks.extend(_finalize_draft(draft, len(chunks)))
            level = element.level or 1
            heading_stack = [
                (heading_level, heading)
                for heading_level, heading in heading_stack
                if heading_level < level
            ]
            heading_stack.append((level, element.text))
            draft = _ChunkDraft()
            previous_caption = None
            continue

        heading_path = [heading for _, heading in heading_stack]
        if element.element_type == ElementType.CAPTION:
            previous_caption = element

        if element.element_type == ElementType.TABLE:
            chunks.extend(_finalize_draft(draft, len(chunks)))
            draft = _ChunkDraft()
            table_chunks = _chunk_table(
                element,
                heading_path,
                previous_caption,
                config,
                start_index=len(chunks),
            )
            chunks.extend(table_chunks)
            previous_caption = None
            continue

        if len(element.markdown) > config.chunk_size:
            chunks.extend(_finalize_draft(draft, len(chunks)))
            draft = _ChunkDraft()
            chunks.extend(
                _chunk_oversized_text(
                    element,
                    heading_path,
                    config,
                    start_index=len(chunks),
                )
            )
            previous_caption = None
            continue

        element_text = _with_heading_context(element.markdown, heading_path)
        proposed_text = _append_text(draft.text, element_text)
        if draft.elements and len(proposed_text) > config.chunk_size:
            chunks.extend(_finalize_draft(draft, len(chunks)))
            draft = _ChunkDraft()

        if not draft.elements:
            draft.heading_path = heading_path
            if heading_path:
                draft.text_parts.extend(
                    f"{'#' * min(index, 6)} {heading}"
                    for index, heading in enumerate(heading_path, start=1)
                )

        draft.text_parts.append(element.markdown)
        draft.elements.append(element)
        if element.element_type != ElementType.CAPTION:
            previous_caption = None

    chunks.extend(_finalize_draft(draft, len(chunks)))
    return chunks


def _finalize_draft(draft: _ChunkDraft, chunk_index: int) -> list[dict[str, object]]:
    if not draft.elements or not draft.text:
        return []
    return [_build_chunk(chunk_index, draft.text, draft.elements, draft.heading_path)]


def _chunk_table(
    element: DocumentElement,
    heading_path: list[str],
    caption: DocumentElement | None,
    config: ChunkingConfig,
    *,
    start_index: int,
) -> list[dict[str, object]]:
    context_parts = _heading_context_parts(heading_path)
    if caption is not None:
        context_parts.append(caption.markdown)

    atomic_text = _append_text("\n\n".join(context_parts), element.markdown)
    elements = [caption, element] if caption is not None else [element]
    chunk_elements_value = [item for item in elements if item is not None]
    if len(atomic_text) <= config.chunk_size:
        return [
            _build_chunk(
                start_index,
                atomic_text,
                chunk_elements_value,
                heading_path,
                table_part={"part": 1, "parts": 1},
            )
        ]

    rows = _table_rows_from_markdown(element.markdown)
    if len(rows) <= 3:
        return [
            _build_chunk(
                start_index,
                atomic_text,
                chunk_elements_value,
                heading_path,
                table_part={"part": 1, "parts": 1},
            )
        ]

    header = rows[0]
    body_rows = rows[2:] if len(rows) > 2 and set(rows[1]) == {"---"} else rows[1:]
    row_groups: list[list[list[str]]] = []
    current_group: list[list[str]] = []
    for row in body_rows:
        candidate_rows = [header, ["---"] * len(header), *current_group, row]
        candidate_text = _append_text(
            "\n\n".join(context_parts),
            _render_rows(candidate_rows),
        )
        if current_group and len(candidate_text) > config.chunk_size:
            row_groups.append(current_group)
            current_group = [row]
        else:
            current_group.append(row)
    if current_group:
        row_groups.append(current_group)

    chunks: list[dict[str, object]] = []
    total_parts = len(row_groups)
    for offset, group in enumerate(row_groups):
        markdown = _render_rows([header, ["---"] * len(header), *group])
        text = _append_text("\n\n".join(context_parts), markdown)
        chunks.append(
            _build_chunk(
                start_index + offset,
                text,
                chunk_elements_value,
                heading_path,
                table_part={"part": offset + 1, "parts": total_parts},
            )
        )
    return chunks


def _chunk_oversized_text(
    element: DocumentElement,
    heading_path: list[str],
    config: ChunkingConfig,
    *,
    start_index: int,
) -> list[dict[str, object]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=config.separators,
    )
    chunks: list[dict[str, object]] = []
    for offset, text_part in enumerate(splitter.split_text(element.markdown)):
        text = _append_text(
            "\n\n".join(_heading_context_parts(heading_path)), text_part
        )
        chunks.append(
            _build_chunk(
                start_index + offset,
                text,
                [element],
                heading_path,
                split_part={"part": offset + 1},
            )
        )
    total_parts = len(chunks)
    for chunk in chunks:
        chunk["metadata"]["split_part"]["parts"] = total_parts
    return chunks


def _build_chunk(
    chunk_index: int,
    text: str,
    elements: list[DocumentElement],
    heading_path: list[str],
    *,
    table_part: dict[str, int] | None = None,
    split_part: dict[str, int] | None = None,
) -> dict[str, object]:
    page_start = min(element.page_start for element in elements)
    page_end = max(element.page_end for element in elements)
    element_types = [element.element_type.value for element in elements]
    heading = heading_path[-1] if heading_path else None
    metadata: dict[str, object] = {
        "heading": heading,
        "heading_path": heading_path,
        "page_range": [page_start, page_end],
        "element_types": element_types,
        "source_elements": [element.to_metadata() for element in elements],
        "bbox_refs": [
            {
                "page": element.page_start,
                "type": element.element_type.value,
                "bbox": element.bbox.to_list(),
            }
            for element in elements
        ],
    }
    table_summaries = [
        element.table.to_dict()
        for element in elements
        if element.element_type == ElementType.TABLE and element.table is not None
    ]
    if table_summaries:
        metadata["tables"] = table_summaries
    if table_part is not None:
        metadata["table_part"] = table_part
    if split_part is not None:
        metadata["split_part"] = split_part

    return {
        "chunk_index": chunk_index,
        "page_start": page_start,
        "page_end": page_end,
        "text": text.strip(),
        "heading": heading,
        "metadata": metadata,
    }


def _with_heading_context(text: str, heading_path: list[str]) -> str:
    return _append_text("\n\n".join(_heading_context_parts(heading_path)), text)


def _heading_context_parts(heading_path: list[str]) -> list[str]:
    return [
        f"{'#' * min(index, 6)} {heading}"
        for index, heading in enumerate(heading_path, start=1)
    ]


def _append_text(prefix: str, suffix: str) -> str:
    if not prefix:
        return suffix.strip()
    if not suffix:
        return prefix.strip()
    return f"{prefix.strip()}\n\n{suffix.strip()}"


def _table_rows_from_markdown(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [
            cell.strip().replace("\\|", "|") for cell in line.strip("|").split("|")
        ]
        rows.append(cells)
    return rows


def _render_rows(rows: list[list[str]]) -> str:
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)

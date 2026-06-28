"""PyMuPDF-based structured PDF extraction and markdown rendering."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import fitz

from src.extraction.models import (
    BoundingBox,
    DocumentElement,
    ElementStyle,
    ElementType,
    StructuredExtractionResult,
    TableMetadata,
)

_BULLET_PREFIXES = ("- ", "* ", "• ", "‣ ", "◦ ")
_NUMBERED_LIST_PATTERN = re.compile(r"^(\d+|[A-Za-z])[\.\)]\s+\S")
_NUMBERING_PATTERN = re.compile(r"^(\d+(\.\d+)*|[A-Z])[\.\)]?\s+\S")
_PAGE_NUMBER_PATTERN = re.compile(r"^(page\s+)?\d+(\s+of\s+\d+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class _RawLine:
    text: str
    page_number: int
    bbox: BoundingBox
    style: ElementStyle
    block_number: int
    line_number: int


@dataclass(frozen=True)
class _DetectedTable:
    markdown: str
    text: str
    page_number: int
    bbox: BoundingBox
    metadata: TableMetadata


async def extract_markdown(pdf_bytes: bytes) -> dict[str, object]:
    """Extract markdown plus legacy page provenance from a PDF."""
    result = await extract_structure(pdf_bytes)
    return result.to_legacy_dict()


async def extract_structure(pdf_bytes: bytes) -> StructuredExtractionResult:
    """Extract typed document elements from PDF bytes without LLM or OCR dependencies."""
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        all_lines: list[_RawLine] = []
        tables_by_page: dict[int, list[_DetectedTable]] = {}

        for page_index, page in enumerate(document, start=1):
            tables = _extract_tables(page, page_index)
            tables_by_page[page_index] = tables
            all_lines.extend(_extract_page_lines(page, page_index))

        filtered_lines = _filter_repeated_headers_and_footers(all_lines)
        body_size = _detect_body_font_size(filtered_lines)
        heading_profiles = _detect_heading_profiles(filtered_lines, body_size)

        elements: list[DocumentElement] = []
        for page_index in range(1, len(document) + 1):
            page_tables = tables_by_page.get(page_index, [])
            for table in page_tables:
                elements.append(
                    DocumentElement(
                        element_type=ElementType.TABLE,
                        text=table.text,
                        markdown=table.markdown,
                        page_start=page_index,
                        page_end=page_index,
                        bbox=table.bbox,
                        table=table.metadata,
                    )
                )

            text_lines = [
                line
                for line in filtered_lines
                if line.page_number == page_index
                and not _overlaps_any_table(line.bbox, page_tables)
            ]
            elements.extend(
                _classify_text_lines(text_lines, body_size, heading_profiles)
            )

        elements.sort(key=_element_sort_key)
        return StructuredExtractionResult(elements=elements)
    finally:
        document.close()


def render_element_markdown(
    element_type: ElementType,
    text: str,
    *,
    level: int | None = None,
    table_rows: list[list[str]] | None = None,
) -> str:
    """Render markdown for a classified element."""
    clean_text = _normalize_inline_text(text)
    if element_type == ElementType.HEADING:
        heading_level = min(max(level or 1, 1), 6)
        return f"{'#' * heading_level} {clean_text}"
    if element_type == ElementType.LIST_ITEM:
        return clean_text if _looks_like_list_item(clean_text) else f"- {clean_text}"
    if element_type == ElementType.TABLE and table_rows is not None:
        return _render_table_markdown(table_rows)
    return clean_text


def _extract_page_lines(page: fitz.Page, page_number: int) -> list[_RawLine]:
    text_dict = page.get_text("dict")
    lines: list[_RawLine] = []

    for block_number, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") != 0:
            continue

        for line_number, line in enumerate(block.get("lines", [])):
            spans = [
                span for span in line.get("spans", []) if span.get("text", "").strip()
            ]
            if not spans:
                continue

            line_text = _normalize_inline_text(
                "".join(span.get("text", "") for span in spans)
            )
            if not line_text:
                continue

            bbox_values = line.get("bbox") or block.get("bbox") or (0, 0, 0, 0)
            dominant_span = max(
                spans,
                key=lambda span: len(str(span.get("text", "")).strip()),
            )
            font_name = str(dominant_span.get("font", ""))
            flags = int(dominant_span.get("flags", 0))
            style = ElementStyle(
                font_size=round(float(dominant_span.get("size", 0.0)), 2),
                font_name=font_name,
                is_bold="bold" in font_name.lower() or bool(flags & 16),
                is_italic="italic" in font_name.lower() or bool(flags & 2),
            )
            lines.append(
                _RawLine(
                    text=line_text,
                    page_number=page_number,
                    bbox=_bbox_from_values(bbox_values),
                    style=style,
                    block_number=block_number,
                    line_number=line_number,
                )
            )

    return sorted(lines, key=_line_sort_key)


def _extract_tables(page: fitz.Page, page_number: int) -> list[_DetectedTable]:
    if not hasattr(page, "find_tables"):
        return []

    try:
        table_finder = page.find_tables()
    except Exception:
        return []

    detected: list[_DetectedTable] = []
    for table in getattr(table_finder, "tables", []) or []:
        rows = _extract_table_rows(table)
        if not rows:
            continue

        bbox_values = getattr(table, "bbox", None) or (0, 0, 0, 0)
        header_rows = [rows[0]] if rows else []
        metadata = TableMetadata(
            row_count=len(rows),
            column_count=max((len(row) for row in rows), default=0),
            has_header=bool(header_rows),
            header_rows=header_rows,
        )
        markdown = render_element_markdown(ElementType.TABLE, "", table_rows=rows)
        detected.append(
            _DetectedTable(
                markdown=markdown,
                text="\n".join(" | ".join(cell for cell in row) for row in rows),
                page_number=page_number,
                bbox=_bbox_from_values(bbox_values),
                metadata=metadata,
            )
        )

    return detected


def _extract_table_rows(table: Any) -> list[list[str]]:
    try:
        extracted = table.extract()
    except Exception:
        extracted = []

    rows: list[list[str]] = []
    for row in extracted or []:
        clean_row = [
            _normalize_inline_text("" if cell is None else str(cell)) for cell in row
        ]
        if any(clean_row):
            rows.append(clean_row)
    return rows


def _filter_repeated_headers_and_footers(lines: list[_RawLine]) -> list[_RawLine]:
    pages = sorted({line.page_number for line in lines})
    if len(pages) < 2:
        return [line for line in lines if not _PAGE_NUMBER_PATTERN.match(line.text)]

    page_heights: dict[int, float] = defaultdict(float)
    for line in lines:
        page_heights[line.page_number] = max(
            page_heights[line.page_number], line.bbox.y1
        )

    candidates: Counter[str] = Counter()
    candidate_lines: dict[str, list[_RawLine]] = defaultdict(list)
    for line in lines:
        page_height = page_heights.get(line.page_number, 0.0)
        top_band = line.bbox.y0 <= max(page_height * 0.12, 72)
        bottom_band = page_height and line.bbox.y1 >= page_height * 0.88
        normalized = _normalize_for_repetition(line.text)
        if normalized and (
            top_band or bottom_band or _PAGE_NUMBER_PATTERN.match(line.text)
        ):
            candidates[normalized] += 1
            candidate_lines[normalized].append(line)

    min_repetitions = max(2, int(len(pages) * 0.6))
    repeated = {
        text
        for text, count in candidates.items()
        if count >= min_repetitions or _PAGE_NUMBER_PATTERN.match(text)
    }

    return [
        line
        for line in lines
        if _normalize_for_repetition(line.text) not in repeated
        and not _PAGE_NUMBER_PATTERN.match(line.text)
    ]


def _detect_body_font_size(lines: list[_RawLine]) -> float:
    sizes: list[float] = []
    for line in lines:
        sizes.extend([round(line.style.font_size, 1)] * max(len(line.text), 1))
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]


def _detect_heading_profiles(
    lines: list[_RawLine], body_size: float
) -> dict[float, int]:
    candidates: list[float] = []
    for line in lines:
        if _is_heading_candidate(line, body_size):
            candidates.append(round(line.style.font_size, 1))

    distinct_sizes = sorted(
        {size for size in candidates if size >= body_size}, reverse=True
    )[:4]
    return {size: min(index, 4) for index, size in enumerate(distinct_sizes, start=1)}


def _classify_text_lines(
    lines: list[_RawLine],
    body_size: float,
    heading_profiles: dict[float, int],
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    paragraph_buffer: list[_RawLine] = []

    for previous_line, line, next_line in _with_neighbors(lines):
        heading_level = _heading_level(
            line, body_size, heading_profiles, previous_line, next_line
        )
        if heading_level is not None:
            elements.extend(_flush_paragraph(paragraph_buffer))
            elements.append(
                DocumentElement(
                    element_type=ElementType.HEADING,
                    text=line.text,
                    markdown=render_element_markdown(
                        ElementType.HEADING, line.text, level=heading_level
                    ),
                    page_start=line.page_number,
                    page_end=line.page_number,
                    bbox=line.bbox,
                    style=line.style,
                    level=heading_level,
                )
            )
            continue

        if _looks_like_list_item(line.text):
            elements.extend(_flush_paragraph(paragraph_buffer))
            elements.append(
                DocumentElement(
                    element_type=ElementType.LIST_ITEM,
                    text=line.text,
                    markdown=render_element_markdown(ElementType.LIST_ITEM, line.text),
                    page_start=line.page_number,
                    page_end=line.page_number,
                    bbox=line.bbox,
                    style=line.style,
                )
            )
            continue

        paragraph_buffer.append(line)

    elements.extend(_flush_paragraph(paragraph_buffer))
    return elements


def _flush_paragraph(lines: list[_RawLine]) -> list[DocumentElement]:
    if not lines:
        return []

    text = " ".join(line.text for line in lines)
    bbox = _merge_bboxes([line.bbox for line in lines])
    first = lines[0]
    last = lines[-1]
    lines.clear()
    return [
        DocumentElement(
            element_type=ElementType.PARAGRAPH,
            text=text,
            markdown=render_element_markdown(ElementType.PARAGRAPH, text),
            page_start=first.page_number,
            page_end=last.page_number,
            bbox=bbox,
            style=first.style,
        )
    ]


def _heading_level(
    line: _RawLine,
    body_size: float,
    heading_profiles: dict[float, int],
    previous_line: _RawLine | None,
    next_line: _RawLine | None,
) -> int | None:
    if not _is_heading_candidate(line, body_size):
        return None

    size = round(line.style.font_size, 1)
    if size in heading_profiles:
        return heading_profiles[size]

    if _NUMBERING_PATTERN.match(line.text) and (
        line.style.is_bold or len(line.text) <= 90
    ):
        return min(len(line.text.split(".", 3)), 4)

    gap_before = line.bbox.y0 - previous_line.bbox.y1 if previous_line else 0.0
    gap_after = next_line.bbox.y0 - line.bbox.y1 if next_line else 0.0
    if line.style.is_bold and len(line.text) <= 120 and max(gap_before, gap_after) >= 4:
        return 3

    return None


def _is_heading_candidate(line: _RawLine, body_size: float) -> bool:
    text = line.text.strip()
    if not text or len(text) > 180 or _looks_like_bullet_item(text):
        return False
    if _looks_like_list_item(text) and not _looks_like_numbered_heading(text):
        return False
    if text.endswith((".", ",", ";", ":")) and not _NUMBERING_PATTERN.match(text):
        return False

    size_signal = line.style.font_size >= body_size * 1.12
    bold_signal = line.style.is_bold and len(text) <= 120
    numbering_signal = bool(_NUMBERING_PATTERN.match(text)) and len(text) <= 140
    title_case_signal = text[:1].isupper() and text.count(" ") <= 12 and len(text) <= 90
    return size_signal or numbering_signal or (bold_signal and title_case_signal)


def _looks_like_list_item(line_text: str) -> bool:
    text = line_text.strip()
    return _looks_like_bullet_item(text) or bool(_NUMBERED_LIST_PATTERN.match(text))


def _looks_like_bullet_item(line_text: str) -> bool:
    return line_text.strip().startswith(_BULLET_PREFIXES)


def _looks_like_numbered_heading(line_text: str) -> bool:
    text = line_text.strip()
    if not _NUMBERING_PATTERN.match(text):
        return False
    remainder = re.sub(r"^(\d+(\.\d+)*|[A-Z])[\.\)]?\s+", "", text, count=1)
    return bool(remainder[:1].isupper()) and len(remainder) <= 120


def _render_table_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header = padded_rows[0]
    separator = ["---"] * column_count
    rendered = [
        "| " + " | ".join(_escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in padded_rows[1:]:
        rendered.append(
            "| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |"
        )
    return "\n".join(rendered)


def _line_sort_key(line: _RawLine) -> tuple[int, int, float, float]:
    return (line.block_number, line.line_number, line.bbox.y0, line.bbox.x0)


def _element_sort_key(element: DocumentElement) -> tuple[int, int, float, float]:
    type_rank = 1 if element.element_type == ElementType.TABLE else 0
    return (element.page_start, type_rank, element.bbox.y0, element.bbox.x0)


def _with_neighbors(
    lines: list[_RawLine],
) -> list[tuple[_RawLine | None, _RawLine, _RawLine | None]]:
    return [
        (
            lines[index - 1] if index > 0 else None,
            line,
            lines[index + 1] if index + 1 < len(lines) else None,
        )
        for index, line in enumerate(lines)
    ]


def _overlaps_any_table(bbox: BoundingBox, tables: list[_DetectedTable]) -> bool:
    return any(bbox.overlap_ratio(table.bbox) >= 0.5 for table in tables)


def _bbox_from_values(values: Any) -> BoundingBox:
    x0, y0, x1, y1 = values
    return BoundingBox(float(x0), float(y0), float(x1), float(y1))


def _merge_bboxes(boxes: list[BoundingBox]) -> BoundingBox:
    return BoundingBox(
        min(box.x0 for box in boxes),
        min(box.y0 for box in boxes),
        max(box.x1 for box in boxes),
        max(box.y1 for box in boxes),
    )


def _normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_for_repetition(text: str) -> str:
    return re.sub(r"\d+", "#", _normalize_inline_text(text).lower())


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()

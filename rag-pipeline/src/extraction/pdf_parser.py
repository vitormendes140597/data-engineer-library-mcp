"""PyMuPDF-based PDF to markdown extraction."""

from __future__ import annotations

from collections import Counter

import fitz


async def extract_markdown(pdf_bytes: bytes) -> dict[str, object]:
    """Extract hierarchy-aware markdown plus page provenance from a PDF."""
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages: list[dict[str, object]] = []
        page_contents: dict[int, str] = {}

        for page_index, page in enumerate(document, start=1):
            page_text, page_markdown, headings = _extract_page_markdown(page)
            page_contents[page_index] = page_markdown
            pages.append(
                {
                    "page_number": page_index,
                    "text": page_text,
                    "markdown": page_markdown,
                    "headings": headings,
                }
            )

        return {
            "text": "\n\n".join(page_contents[page] for page in sorted(page_contents)),
            "pages": pages,
            "page_contents": page_contents,
        }
    finally:
        document.close()


def _extract_page_markdown(page: fitz.Page) -> tuple[str, str, list[dict[str, object]]]:
    text_dict = page.get_text("dict")
    body_size = _detect_body_font_size(text_dict)
    heading_sizes = _detect_heading_sizes(text_dict, body_size)

    raw_lines: list[str] = []
    markdown_lines: list[str] = []
    headings: list[dict[str, object]] = []
    paragraph_buffer: list[str] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = [
                span for span in line.get("spans", []) if span.get("text", "").strip()
            ]
            if not spans:
                continue

            line_text = "".join(span.get("text", "") for span in spans).strip()
            if not line_text:
                continue

            raw_lines.append(line_text)
            max_size = max(
                round(float(span.get("size", body_size)), 1) for span in spans
            )
            heading_level = heading_sizes.get(max_size)
            if heading_level is not None and len(line_text) <= 200:
                _flush_paragraph(paragraph_buffer, markdown_lines)
                headings.append({"text": line_text, "level": heading_level})
                markdown_lines.append(f"{'#' * heading_level} {line_text}")
                continue

            if _looks_like_list_item(line_text):
                _flush_paragraph(paragraph_buffer, markdown_lines)
                markdown_lines.append(line_text)
                continue

            paragraph_buffer.append(line_text)

        _flush_paragraph(paragraph_buffer, markdown_lines)

    _flush_paragraph(paragraph_buffer, markdown_lines)
    page_text = "\n".join(raw_lines)
    page_markdown = "\n\n".join(line for line in markdown_lines if line.strip())
    return page_text, page_markdown, headings


def _detect_body_font_size(text_dict: dict[str, object]) -> float:
    sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if text.strip():
                    size = round(float(span.get("size", 0.0)), 1)
                    sizes.extend([size] * max(len(text.strip()), 1))

    if not sizes:
        return 12.0

    counts = Counter(sizes)
    return counts.most_common(1)[0][0]


def _detect_heading_sizes(
    text_dict: dict[str, object], body_size: float
) -> dict[float, int]:
    candidate_sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [
                span for span in line.get("spans", []) if span.get("text", "").strip()
            ]
            if not spans:
                continue
            max_size = max(
                round(float(span.get("size", body_size)), 1) for span in spans
            )
            if max_size > body_size * 1.05:
                candidate_sizes.append(max_size)

    distinct_sizes = sorted(set(candidate_sizes), reverse=True)[:3]
    if not distinct_sizes:
        return {}

    if len(distinct_sizes) == 1 and distinct_sizes[0] < body_size * 1.15:
        return {}

    heading_map: dict[float, int] = {}
    for index, size in enumerate(distinct_sizes, start=1):
        heading_map[size] = min(index, 3)
    return heading_map


def _flush_paragraph(paragraph_buffer: list[str], markdown_lines: list[str]) -> None:
    if not paragraph_buffer:
        return
    markdown_lines.append(" ".join(paragraph_buffer))
    paragraph_buffer.clear()


def _looks_like_list_item(line_text: str) -> bool:
    return line_text.startswith(("- ", "* ", "• ")) or (
        len(line_text) > 2 and line_text[0].isdigit() and line_text[1:3] in {". ", ") "}
    )

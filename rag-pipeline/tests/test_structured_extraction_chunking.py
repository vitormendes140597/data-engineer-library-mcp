from __future__ import annotations

import fitz
import pytest

from src.chunking.chunker import chunk_elements
from src.config import ChunkingConfig
from src.extraction.models import (
    BoundingBox,
    DocumentElement,
    ElementType,
    TableMetadata,
)
from src.extraction.pdf_parser import extract_structure


def _simple_pdf(lines: list[tuple[float, float, str, int]]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    for x, y, text, size in lines:
        page.insert_text((x, y), text, fontsize=size)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_extract_structure_returns_elements_with_provenance_and_bounding_boxes():
    result = await extract_structure(
        _simple_pdf(
            [
                (72, 72, "Document Title", 24),
                (72, 120, "This paragraph has provenance.", 12),
            ]
        )
    )

    assert result.elements[0].element_type == ElementType.HEADING
    assert result.elements[0].page_start == 1
    assert result.elements[0].bbox.x1 > result.elements[0].bbox.x0
    assert result.page_contents[1].startswith("# Document Title")
    assert "elements" in result.to_legacy_dict()


@pytest.mark.asyncio
async def test_heading_detection_uses_style_without_promoting_plain_short_text():
    result = await extract_structure(
        _simple_pdf(
            [
                (72, 72, "1. Overview", 12),
                (72, 110, "Tiny", 12),
                (72, 140, "normal body content continues here.", 12),
            ]
        )
    )

    headings = [element.text for element in result.elements if element.level]

    assert "1. Overview" in headings
    assert "Tiny" not in headings


@pytest.mark.asyncio
async def test_list_item_boundaries_are_preserved():
    result = await extract_structure(
        _simple_pdf(
            [
                (72, 72, "Shopping", 18),
                (72, 110, "- first item", 12),
                (72, 130, "- second item", 12),
            ]
        )
    )

    list_items = [
        element
        for element in result.elements
        if element.element_type == ElementType.LIST_ITEM
    ]

    assert [item.text for item in list_items] == ["- first item", "- second item"]


@pytest.mark.asyncio
async def test_repeated_header_footer_and_page_numbers_are_filtered():
    document = fitz.open()
    for page_number in range(1, 4):
        page = document.new_page()
        page.insert_text((72, 36), "Repeated Header", fontsize=10)
        page.insert_text((72, 120), f"Unique body {page_number}", fontsize=12)
        page.insert_text((72, 780), str(page_number), fontsize=10)
    pdf_bytes = document.tobytes()
    document.close()

    result = await extract_structure(pdf_bytes)
    text = result.text

    assert "Repeated Header" not in text
    assert "Unique body 1" in text
    assert "\n1\n" not in text


@pytest.mark.asyncio
async def test_table_extraction_renders_markdown_and_suppresses_duplicate_text():
    if not hasattr(fitz.Page, "find_tables"):
        pytest.skip("Installed PyMuPDF does not expose table detection")

    document = fitz.open()
    page = document.new_page()
    xs = [72, 160, 248]
    ys = [72, 100, 128, 156]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    page.insert_text((82, 92), "Name", fontsize=10)
    page.insert_text((170, 92), "Value", fontsize=10)
    page.insert_text((82, 120), "Alpha", fontsize=10)
    page.insert_text((170, 120), "10", fontsize=10)
    page.insert_text((82, 148), "Beta", fontsize=10)
    page.insert_text((170, 148), "20", fontsize=10)
    pdf_bytes = document.tobytes()
    document.close()

    result = await extract_structure(pdf_bytes)
    tables = [
        element
        for element in result.elements
        if element.element_type == ElementType.TABLE
    ]
    paragraphs = [
        element.text
        for element in result.elements
        if element.element_type == ElementType.PARAGRAPH
    ]

    assert tables
    assert "| Name | Value |" in tables[0].markdown
    assert tables[0].table is not None
    assert tables[0].table.row_count >= 2
    assert not any("Alpha" in paragraph for paragraph in paragraphs)


@pytest.mark.asyncio
async def test_chunk_elements_preserves_heading_path_and_page_range():
    elements = [
        DocumentElement(
            ElementType.HEADING,
            "Chapter",
            "# Chapter",
            1,
            1,
            BoundingBox(0, 0, 10, 10),
            level=1,
        ),
        DocumentElement(
            ElementType.HEADING,
            "Section",
            "## Section",
            2,
            2,
            BoundingBox(0, 0, 10, 10),
            level=2,
        ),
        DocumentElement(
            ElementType.PARAGRAPH,
            "body",
            "body",
            2,
            3,
            BoundingBox(0, 10, 10, 20),
        ),
    ]

    chunks = await chunk_elements(
        elements, ChunkingConfig(chunk_size=200, chunk_overlap=20)
    )

    assert chunks[0]["page_start"] == 2
    assert chunks[0]["page_end"] == 3
    assert chunks[0]["metadata"]["heading_path"] == ["Chapter", "Section"]
    assert chunks[0]["text"].startswith("# Chapter\n\n## Section")


@pytest.mark.asyncio
async def test_chunk_elements_keeps_small_tables_atomic_and_splits_large_tables():
    small_table = DocumentElement(
        ElementType.TABLE,
        "H | V\nA | 1",
        "| H | V |\n| --- | --- |\n| A | 1 |",
        1,
        1,
        BoundingBox(0, 0, 20, 20),
        table=TableMetadata(row_count=2, column_count=2, has_header=True),
    )
    large_table_rows = "\n".join(
        f"| Row {index} | Value {index} |" for index in range(12)
    )
    large_table = DocumentElement(
        ElementType.TABLE,
        large_table_rows,
        "| H | V |\n| --- | --- |\n" + large_table_rows,
        2,
        2,
        BoundingBox(0, 0, 20, 20),
        table=TableMetadata(row_count=13, column_count=2, has_header=True),
    )

    small_chunks = await chunk_elements(
        [small_table], ChunkingConfig(chunk_size=200, chunk_overlap=20)
    )
    large_chunks = await chunk_elements(
        [large_table], ChunkingConfig(chunk_size=90, chunk_overlap=10)
    )

    assert len(small_chunks) == 1
    assert small_chunks[0]["metadata"]["element_types"] == ["table"]
    assert len(large_chunks) > 1
    assert all("table_part" in chunk["metadata"] for chunk in large_chunks)

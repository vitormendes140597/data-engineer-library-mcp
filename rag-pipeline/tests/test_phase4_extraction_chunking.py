import fitz
import pytest

from src.chunking.chunker import chunk_text
from src.chunking.image_linking import (link_chunks_to_images,
                                        store_chunk_image_links)
from src.config import ChunkingConfig
from src.extraction.pdf_parser import extract_markdown


@pytest.mark.asyncio
async def test_extract_markdown_preserves_page_content_and_headings():
    document = fitz.open()
    page_one = document.new_page()
    page_one.insert_text((72, 72), "Document Title", fontsize=24)
    page_one.insert_text((72, 110), "Section Heading", fontsize=18)
    page_one.insert_text((72, 150), "Body content on the first page.", fontsize=12)

    page_two = document.new_page()
    page_two.insert_text((72, 72), "Continuation on the second page.", fontsize=12)

    pdf_bytes = document.tobytes()
    document.close()

    result = await extract_markdown(pdf_bytes)

    assert result["page_contents"][1].startswith("# Document Title")
    assert "## Section Heading" in result["page_contents"][1]
    assert result["pages"][1]["text"] == "Continuation on the second page."
    assert "Continuation on the second page." in result["text"]


@pytest.mark.asyncio
async def test_chunk_text_tracks_page_ranges_and_heading_metadata():
    markdown_pages = {
        1: "# Intro\n\n" + ("alpha " * 20),
        2: "## Details\n\n" + ("beta " * 20),
    }
    config = ChunkingConfig(chunk_size=400, chunk_overlap=25)

    chunks = await chunk_text(markdown_pages, config)

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 2
    assert chunks[0]["heading"] == "Intro"
    assert chunks[0]["metadata"]["page_range"] == [1, 2]


@pytest.mark.asyncio
async def test_link_chunks_to_images_uses_inclusive_page_ranges():
    chunks = [
        {"chunk_index": 0, "page_start": 1, "page_end": 2},
        {"chunk_index": 1, "page_start": 3, "page_end": 3},
    ]
    images = [
        {"source_page": 2},
        {"source_page": 3},
        {"source_page": 4},
    ]

    links = await link_chunks_to_images(chunks, images)
    stored_links = await store_chunk_image_links(
        ["chunk-0", "chunk-1"], ["image-0", "image-1", "image-2"], links
    )

    assert links == [(0, 0), (1, 1)]
    assert stored_links == [("chunk-0", "image-0"), ("chunk-1", "image-1")]

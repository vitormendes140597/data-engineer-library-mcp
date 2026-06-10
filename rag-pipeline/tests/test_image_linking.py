"""Unit tests for deterministic chunk-to-image linking."""

from __future__ import annotations

import pytest

from src.chunking.image_linking import link_chunks_to_images, store_chunk_image_links


@pytest.mark.asyncio
async def test_chunks_spanning_pages_two_through_four_link_all_images_in_range() -> None:
    chunks = [{"chunk_index": 0, "page_start": 2, "page_end": 4}]
    images = [
        {"source_page": 2},
        {"source_page": 3},
        {"source_page": 4},
    ]

    links = await link_chunks_to_images(chunks, images)

    assert links == [(0, 0), (0, 1), (0, 2)]


@pytest.mark.asyncio
async def test_no_images_in_range_creates_no_links() -> None:
    links = await link_chunks_to_images(
        [{"chunk_index": 0, "page_start": 5, "page_end": 6}],
        [{"source_page": 2}, {"source_page": 7}],
    )

    assert links == []


@pytest.mark.asyncio
async def test_image_outside_range_is_not_linked() -> None:
    links = await link_chunks_to_images(
        [{"chunk_index": 0, "page_start": 2, "page_end": 4}],
        [{"source_page": 1}, {"source_page": 5}],
    )

    assert links == []


@pytest.mark.asyncio
async def test_multiple_chunks_with_overlapping_ranges_link_deterministically() -> None:
    chunks = [
        {"chunk_index": 0, "page_start": 1, "page_end": 3},
        {"chunk_index": 1, "page_start": 3, "page_end": 5},
    ]
    images = [
        {"source_page": 2},
        {"source_page": 3},
        {"source_page": 4},
    ]

    links = await link_chunks_to_images(chunks, images)
    stored_links = await store_chunk_image_links(
        ["chunk-0", "chunk-1"],
        ["image-0", "image-1", "image-2"],
        links,
    )

    assert links == [(0, 0), (0, 1), (1, 1), (1, 2)]
    assert stored_links == [
        ("chunk-0", "image-0"),
        ("chunk-0", "image-1"),
        ("chunk-1", "image-1"),
        ("chunk-1", "image-2"),
    ]


@pytest.mark.asyncio
async def test_single_page_chunk_links_only_images_on_that_page() -> None:
    links = await link_chunks_to_images(
        [{"chunk_index": 2, "page_start": 7, "page_end": 7}],
        [{"source_page": 6}, {"source_page": 7}, {"source_page": 8}],
    )

    assert links == [(2, 1)]

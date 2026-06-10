"""Chunk-to-image linking helpers."""

from __future__ import annotations

from typing import Any


async def link_chunks_to_images(
    chunks: list[dict[str, Any]], images: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    """Return chunk/image index pairs for images whose pages fall within chunk ranges."""
    links: list[tuple[int, int]] = []
    for chunk in chunks:
        page_start = int(chunk["page_start"])
        page_end = int(chunk["page_end"])
        chunk_index = int(chunk["chunk_index"])

        for image_index, image in enumerate(images):
            source_page = int(image["source_page"])
            if page_start <= source_page <= page_end:
                links.append((chunk_index, image_index))

    return links


async def store_chunk_image_links(
    chunk_ids: list[Any],
    image_ids: list[Any],
    links: list[tuple[int, int]],
) -> list[tuple[Any, Any]]:
    """Resolve chunk/image index pairs into database-ready identifier pairs."""
    stored_links: list[tuple[Any, Any]] = []
    for chunk_index, image_index in links:
        stored_links.append((chunk_ids[chunk_index], image_ids[image_index]))
    return stored_links

"""Integration tests for repository operations against PostgreSQL pgvector."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.config import VECTOR_DIMENSION
from src.persistence.models import ChunkImage
from src.persistence.repository import (
    ChunkCreate,
    ChunkImageLinkCreate,
    DocumentCreate,
    ImageCreate,
)


@pytest.mark.asyncio
async def test_insert_document_and_retrieve_it(repository: object) -> None:
    created = await repository.create_document(
        DocumentCreate(
            blob_url="https://example.com/raw-pdfs/doc-1.pdf",
            content_length=123,
            etag='"etag-1"',
            status="completed",
        )
    )

    fetched = await repository.get_document_by_blob_url(created.blob_url)

    assert fetched is not None
    assert str(fetched.id) == str(created.id)
    assert fetched.content_length == 123
    assert fetched.etag == '"etag-1"'


@pytest.mark.asyncio
async def test_insert_chunks_with_pgvector_embeddings(repository: object) -> None:
    replacement = await repository.replace_document_contents(
        DocumentCreate(
            blob_url="https://example.com/raw-pdfs/doc-2.pdf",
            content_length=456,
            etag='"etag-2"',
            status="completed",
        ),
        chunks=[
            ChunkCreate(
                chunk_index=0,
                page_start=1,
                page_end=2,
                text="Chunk one",
                embedding=[0.1] * VECTOR_DIMENSION,
                metadata={"heading": "Intro"},
            )
        ],
        images=[],
        chunk_image_links=[],
    )

    fetched = await repository.get_document_by_blob_url(replacement.document.blob_url)

    assert fetched is not None
    assert len(fetched.chunks) == 1
    assert list(fetched.chunks[0].embedding) == pytest.approx([0.1] * VECTOR_DIMENSION)
    assert fetched.chunks[0].metadata_json == {"heading": "Intro"}


@pytest.mark.asyncio
async def test_transactional_replacement_removes_old_chunks_and_inserts_new_rows(
    repository: object,
) -> None:
    first = await repository.replace_document_contents(
        DocumentCreate(
            blob_url="https://example.com/raw-pdfs/doc-3.pdf",
            content_length=100,
            etag='"etag-old"',
            status="completed",
        ),
        chunks=[
            ChunkCreate(
                chunk_index=0,
                page_start=1,
                page_end=1,
                text="Old chunk",
                embedding=[0.2] * VECTOR_DIMENSION,
            )
        ],
        images=[
            ImageCreate(
                blob_path="images/doc-3/old.png",
                blob_url="https://example.com/extracted-images/doc-3/old.png",
                source_page=1,
                image_format="png",
            )
        ],
        chunk_image_links=[ChunkImageLinkCreate(chunk_index=0, image_index=0)],
    )

    second = await repository.replace_document_contents(
        DocumentCreate(
            blob_url=first.document.blob_url,
            content_length=200,
            etag='"etag-new"',
            status="completed",
        ),
        chunks=[
            ChunkCreate(
                chunk_index=0,
                page_start=2,
                page_end=2,
                text="New chunk",
                embedding=[0.3] * VECTOR_DIMENSION,
            )
        ],
        images=[
            ImageCreate(
                blob_path="images/doc-3/new.png",
                blob_url="https://example.com/extracted-images/doc-3/new.png",
                source_page=2,
                image_format="png",
            )
        ],
        chunk_image_links=[ChunkImageLinkCreate(chunk_index=0, image_index=0)],
    )

    fetched = await repository.get_document_by_blob_url(first.document.blob_url)

    assert second.replaced_image_paths == ["images/doc-3/old.png"]
    assert fetched is not None
    assert len(fetched.chunks) == 1
    assert fetched.chunks[0].text == "New chunk"
    assert len(fetched.images) == 1
    assert fetched.images[0].blob_path == "images/doc-3/new.png"


@pytest.mark.asyncio
async def test_chunk_image_linking_is_persisted_in_database(repository: object) -> None:
    replacement = await repository.replace_document_contents(
        DocumentCreate(
            blob_url="https://example.com/raw-pdfs/doc-4.pdf",
            content_length=789,
            etag='"etag-4"',
            status="completed",
        ),
        chunks=[
            ChunkCreate(
                chunk_index=0,
                page_start=2,
                page_end=4,
                text="Chunk spanning pages 2-4",
                embedding=[0.4] * VECTOR_DIMENSION,
            ),
            ChunkCreate(
                chunk_index=1,
                page_start=4,
                page_end=4,
                text="Chunk on page 4",
                embedding=[0.5] * VECTOR_DIMENSION,
            ),
        ],
        images=[
            ImageCreate(
                blob_path="images/doc-4/page2.png",
                blob_url="https://example.com/extracted-images/doc-4/page2.png",
                source_page=2,
                image_format="png",
            ),
            ImageCreate(
                blob_path="images/doc-4/page4.png",
                blob_url="https://example.com/extracted-images/doc-4/page4.png",
                source_page=4,
                image_format="png",
            ),
        ],
        chunk_image_links=[
            ChunkImageLinkCreate(chunk_index=0, image_index=0),
            ChunkImageLinkCreate(chunk_index=0, image_index=1),
            ChunkImageLinkCreate(chunk_index=1, image_index=1),
        ],
    )

    async with repository._session_factory() as session:  # noqa: SLF001
        stored_links = (
            (
                await session.execute(
                    select(ChunkImage).where(
                        ChunkImage.chunk_id.in_(
                            [chunk.id for chunk in replacement.chunks]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(stored_links) == 3
    assert {str(link.chunk_id) for link in stored_links} == {
        str(replacement.chunks[0].id),
        str(replacement.chunks[1].id),
    }

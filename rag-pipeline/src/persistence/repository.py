"""Async repository methods for RAG persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import selectinload

from src.blob.client import BlobClient
from src.config import DatabaseConfig, RetryConfig
from src.persistence.models import (DOCUMENT_STATUS_PENDING,
                                    FAILURE_STATUS_CLAIMED,
                                    FAILURE_STATUS_PENDING,
                                    FAILURE_STATUS_PERMANENTLY_FAILED,
                                    FAILURE_STATUS_RESOLVED, Chunk, ChunkImage,
                                    Document, Image, ProcessingFailure)


@dataclass(slots=True)
class DocumentCreate:
    """Payload for creating or replacing a document."""

    blob_url: str
    content_length: int
    etag: str | None = None
    status: str = DOCUMENT_STATUS_PENDING
    failure_count: int = 0


@dataclass(slots=True)
class ChunkCreate:
    """Payload for storing a document chunk."""

    chunk_index: int
    page_start: int
    page_end: int
    text: str
    embedding: Sequence[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageCreate:
    """Payload for storing an extracted image."""

    blob_path: str
    blob_url: str
    source_page: int
    width: int | None = None
    height: int | None = None
    image_format: str | None = None
    bbox: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChunkImageLinkCreate:
    """Payload for linking a stored chunk to a stored image by sequence position."""

    chunk_index: int
    image_index: int


@dataclass(slots=True)
class ProcessingFailureCreate:
    """Payload for recording a processing failure."""

    blob_url: str
    event_payload: Any
    failure_stage: str
    error_message: str
    error_traceback: str
    attempt_count: int = 1
    status: str = FAILURE_STATUS_PENDING
    next_retry_at: datetime | None = None


@dataclass(slots=True)
class ReplacementResult:
    """Result of replacing a document and its dependent rows."""

    document: Document
    chunks: list[Chunk]
    images: list[Image]
    chunk_images: list[ChunkImage]
    replaced_image_paths: list[str]


def _normalize_async_database_url(database_url: str) -> str:
    """Normalize the configured URL for SQLAlchemy async usage."""
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")
    return str(url)


def _coerce_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _coerce_datetime(value: datetime | float | int | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _serialize_failure(failure: ProcessingFailure) -> dict[str, Any]:
    return {
        "id": str(failure.id),
        "blob_url": failure.blob_url,
        "event_payload": failure.event_payload,
        "failure_stage": failure.failure_stage,
        "error_message": failure.error_message,
        "error_traceback": failure.error_traceback,
        "attempt_count": failure.attempt_count,
        "status": failure.status,
        "next_retry_at": failure.next_retry_at,
        "created_at": failure.created_at,
        "updated_at": failure.updated_at,
    }


class Repository:
    """Async SQLAlchemy repository for RAG persistence operations."""

    def __init__(
        self,
        database_config: DatabaseConfig,
        blob_client: BlobClient | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self._engine = create_async_engine(
            _normalize_async_database_url(database_config.connection_string),
            echo=database_config.echo_sql,
            pool_size=database_config.pool_size,
            max_overflow=database_config.max_overflow,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._blob_client = blob_client
        self._retry_config = retry_config or RetryConfig()

    async def dispose(self) -> None:
        """Dispose database connections."""
        await self._engine.dispose()

    async def get_document_by_blob_url(self, blob_url: str) -> Document | None:
        """Fetch a document by its source blob URL."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Document)
                .options(selectinload(Document.chunks), selectinload(Document.images))
                .where(Document.blob_url == blob_url)
            )
            return result.scalar_one_or_none()

    async def create_document(self, payload: DocumentCreate) -> Document:
        """Create a new document row."""
        async with self._session_factory.begin() as session:
            document = Document(
                blob_url=payload.blob_url,
                content_length=payload.content_length,
                etag=payload.etag,
                status=payload.status,
                failure_count=payload.failure_count,
            )
            session.add(document)
            await session.flush()
            return document

    async def update_document(
        self, document_id: str | UUID, **values: Any
    ) -> Document | None:
        """Update a document with the provided values."""
        async with self._session_factory.begin() as session:
            document = await session.get(Document, _coerce_uuid(document_id))
            if document is None:
                return None

            for key, value in values.items():
                setattr(document, key, value)

            await session.flush()
            return document

    async def update_document_status(
        self,
        document_id: str | UUID,
        status: str,
        *,
        failure_count: int | None = None,
    ) -> Document | None:
        """Update document status and optional failure count."""
        values: dict[str, Any] = {"status": status}
        if failure_count is not None:
            values["failure_count"] = failure_count
        return await self.update_document(document_id, **values)

    async def increment_document_failure_count(
        self, document_id: str | UUID
    ) -> Document | None:
        """Increment the failure counter for a document."""
        async with self._session_factory.begin() as session:
            document = await session.get(Document, _coerce_uuid(document_id))
            if document is None:
                return None
            document.failure_count += 1
            await session.flush()
            return document

    async def delete_document_by_blob_url(self, blob_url: str) -> list[str]:
        """Delete a document and return associated extracted image paths."""
        return await self.delete_document_content(blob_url)

    async def delete_document_content(self, blob_url: str) -> list[str]:
        """Delete a document, dependents, and extracted image blobs for a blob URL."""
        deleted_image_paths: list[str] = []
        async with self._session_factory() as session:
            async with session.begin():
                document = await self._get_document_for_replace(session, blob_url)
                if document is None:
                    return []

                deleted_image_paths = [image.blob_path for image in document.images]
                await session.delete(document)

        if self._blob_client is not None:
            for blob_path in deleted_image_paths:
                await self._blob_client.delete_extracted_image_blob(blob_path)

        return deleted_image_paths

    async def replace_document_contents(
        self,
        document_payload: DocumentCreate,
        chunks: Sequence[ChunkCreate],
        images: Sequence[ImageCreate],
        chunk_image_links: Sequence[ChunkImageLinkCreate] | None = None,
    ) -> ReplacementResult:
        """Replace a document and all dependent rows in a single transaction."""
        return await self.store_document_with_chunks(
            document_id=None,
            document_blob_url=document_payload.blob_url,
            content_length=document_payload.content_length,
            etag=document_payload.etag,
            chunks_with_embeddings=chunks,
            image_metadata=images,
            chunk_image_links=chunk_image_links or [],
            status=document_payload.status,
            failure_count=document_payload.failure_count,
        )

    async def store_document_with_chunks(
        self,
        document_id: str | UUID | None,
        document_blob_url: str,
        content_length: int,
        etag: str | None,
        chunks_with_embeddings: Sequence[ChunkCreate | dict[str, Any]],
        image_metadata: Sequence[ImageCreate | dict[str, Any]],
        chunk_image_links: Sequence[
            ChunkImageLinkCreate | tuple[int, int] | dict[str, Any]
        ],
        *,
        status: str = DOCUMENT_STATUS_PENDING,
        failure_count: int = 0,
    ) -> ReplacementResult:
        """Store a document, chunks, images, and links in a single transaction."""
        coerced_document_id = (
            _coerce_uuid(document_id) if document_id is not None else None
        )
        coerced_chunks = [
            self._coerce_chunk_create(chunk) for chunk in chunks_with_embeddings
        ]
        coerced_images = [self._coerce_image_create(image) for image in image_metadata]
        coerced_links = [
            self._coerce_chunk_image_link_create(link) for link in chunk_image_links
        ]

        async with self._session_factory() as session:
            async with session.begin():
                existing_document = await self._get_document_for_store(
                    session,
                    blob_url=document_blob_url,
                    document_id=coerced_document_id,
                )
                replaced_image_paths = (
                    [image.blob_path for image in existing_document.images]
                    if existing_document is not None
                    else []
                )
                target_document_id = coerced_document_id or (
                    existing_document.id if existing_document is not None else None
                )

                if existing_document is not None:
                    await session.delete(existing_document)
                    await session.flush()

                document_values: dict[str, Any] = {
                    "blob_url": document_blob_url,
                    "content_length": content_length,
                    "etag": etag,
                    "status": status,
                    "failure_count": failure_count,
                }
                if target_document_id is not None:
                    document_values["id"] = target_document_id

                document = Document(**document_values)
                session.add(document)
                await session.flush()

                stored_images = await self._store_images(
                    session, document.id, coerced_images
                )
                stored_chunks = await self._store_chunks(
                    session, document.id, coerced_chunks
                )
                stored_chunk_images = await self._link_chunk_images_by_index(
                    session,
                    stored_chunks,
                    stored_images,
                    coerced_links,
                )

                return ReplacementResult(
                    document=document,
                    chunks=stored_chunks,
                    images=stored_images,
                    chunk_images=stored_chunk_images,
                    replaced_image_paths=replaced_image_paths,
                )

    async def store_chunks(
        self, document_id: str | UUID, chunks: Sequence[ChunkCreate]
    ) -> list[Chunk]:
        """Store chunks for an existing document."""
        async with self._session_factory.begin() as session:
            return await self._store_chunks(session, _coerce_uuid(document_id), chunks)

    async def store_images(
        self, document_id: str | UUID, images: Sequence[ImageCreate]
    ) -> list[Image]:
        """Store extracted images for an existing document."""
        async with self._session_factory.begin() as session:
            return await self._store_images(session, _coerce_uuid(document_id), images)

    async def store_image_metadata(
        self,
        document_id: str | UUID,
        image_metadata: ImageCreate | dict[str, Any],
    ) -> UUID:
        """Store one extracted image metadata row and return its identifier."""
        payload = (
            image_metadata
            if isinstance(image_metadata, ImageCreate)
            else ImageCreate(
                blob_path=image_metadata["blob_path"],
                blob_url=image_metadata["blob_url"],
                source_page=image_metadata["source_page"],
                width=image_metadata.get("width"),
                height=image_metadata.get("height"),
                image_format=image_metadata.get("format"),
                bbox=image_metadata.get("bbox"),
                metadata=image_metadata.get("metadata", {}),
            )
        )
        stored_images = await self.store_images(document_id, [payload])
        return stored_images[0].id

    async def link_chunk_images(
        self, links: Sequence[tuple[str | UUID, str | UUID]]
    ) -> list[ChunkImage]:
        """Create chunk-image association rows."""
        async with self._session_factory.begin() as session:
            chunk_images = [
                ChunkImage(
                    chunk_id=_coerce_uuid(chunk_id), image_id=_coerce_uuid(image_id)
                )
                for chunk_id, image_id in links
            ]
            session.add_all(chunk_images)
            await session.flush()
            return chunk_images

    async def record_failure(
        self,
        blob_url: str,
        event_payload: Any,
        failure_stage: str,
        error_message: str,
        error_traceback: str,
    ) -> str:
        """Persist a durable processing failure record and return its identifier."""
        next_retry_at = datetime.now(timezone.utc) + timedelta(
            seconds=self._retry_config.initial_delay_seconds
        )
        async with self._session_factory.begin() as session:
            failure = ProcessingFailure(
                blob_url=blob_url,
                event_payload=event_payload,
                failure_stage=failure_stage,
                error_message=error_message,
                error_traceback=error_traceback,
                attempt_count=1,
                status=FAILURE_STATUS_PENDING,
                next_retry_at=next_retry_at,
            )
            session.add(failure)
            await session.flush()
            return str(failure.id)

    async def get_due_pending_failures(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return pending failures eligible for retry."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ProcessingFailure)
                .where(
                    ProcessingFailure.status == FAILURE_STATUS_PENDING,
                    ProcessingFailure.next_retry_at <= datetime.now(timezone.utc),
                )
                .order_by(ProcessingFailure.next_retry_at.asc())
                .limit(limit)
            )
            return [_serialize_failure(failure) for failure in result.scalars().all()]

    async def claim_failure(self, failure_id: str | UUID) -> bool:
        """Claim a pending failure row using database locking."""
        async with self._session_factory.begin() as session:
            result = await session.execute(
                select(ProcessingFailure)
                .where(
                    ProcessingFailure.id == _coerce_uuid(failure_id),
                    ProcessingFailure.status == FAILURE_STATUS_PENDING,
                )
                .with_for_update(skip_locked=True)
            )
            failure = result.scalar_one_or_none()
            if failure is None:
                return False

            failure.status = FAILURE_STATUS_CLAIMED
            failure.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return True

    async def reschedule_failure(
        self,
        failure_id: str | UUID,
        next_retry_at: datetime | float | int,
        attempt_count: int,
        *,
        error_message: str | None = None,
        error_traceback: str | None = None,
    ) -> ProcessingFailure | None:
        """Return a claimed failure to the pending state for a future retry."""
        async with self._session_factory.begin() as session:
            failure = await session.get(ProcessingFailure, _coerce_uuid(failure_id))
            if failure is None:
                return None

            failure.status = FAILURE_STATUS_PENDING
            failure.attempt_count = attempt_count
            failure.next_retry_at = _coerce_datetime(next_retry_at)
            failure.updated_at = datetime.now(timezone.utc)
            if error_message is not None:
                failure.error_message = error_message
            if error_traceback is not None:
                failure.error_traceback = error_traceback
            await session.flush()
            return failure

    async def mark_failure_resolved(
        self, failure_id: str | UUID
    ) -> ProcessingFailure | None:
        """Mark a failure as resolved."""
        async with self._session_factory.begin() as session:
            failure = await session.get(ProcessingFailure, _coerce_uuid(failure_id))
            if failure is None:
                return None
            failure.status = FAILURE_STATUS_RESOLVED
            failure.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return failure

    async def mark_failure_permanently_failed(
        self, failure_id: str | UUID
    ) -> ProcessingFailure | None:
        """Mark a failure as permanently failed."""
        async with self._session_factory.begin() as session:
            failure = await session.get(ProcessingFailure, _coerce_uuid(failure_id))
            if failure is None:
                return None
            failure.status = FAILURE_STATUS_PERMANENTLY_FAILED
            failure.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return failure

    async def _get_document_for_replace(
        self, session: AsyncSession, blob_url: str
    ) -> Document | None:
        result = await session.execute(
            select(Document)
            .options(selectinload(Document.images), selectinload(Document.chunks))
            .where(Document.blob_url == blob_url)
        )
        return result.scalar_one_or_none()

    async def _get_document_for_store(
        self,
        session: AsyncSession,
        *,
        blob_url: str,
        document_id: UUID | None,
    ) -> Document | None:
        if document_id is not None:
            result = await session.execute(
                select(Document)
                .options(selectinload(Document.images), selectinload(Document.chunks))
                .where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            if document is not None:
                return document

        return await self._get_document_for_replace(session, blob_url)

    @staticmethod
    def _coerce_chunk_create(chunk: ChunkCreate | dict[str, Any]) -> ChunkCreate:
        if isinstance(chunk, ChunkCreate):
            return chunk
        return ChunkCreate(
            chunk_index=chunk["chunk_index"],
            page_start=chunk["page_start"],
            page_end=chunk["page_end"],
            text=chunk["text"],
            embedding=chunk["embedding"],
            metadata=chunk.get("metadata", {}),
        )

    @staticmethod
    def _coerce_image_create(image: ImageCreate | dict[str, Any]) -> ImageCreate:
        if isinstance(image, ImageCreate):
            return image
        return ImageCreate(
            blob_path=image["blob_path"],
            blob_url=image["blob_url"],
            source_page=image["source_page"],
            width=image.get("width"),
            height=image.get("height"),
            image_format=image.get("format") or image.get("image_format"),
            bbox=image.get("bbox"),
            metadata=image.get("metadata", {}),
        )

    @staticmethod
    def _coerce_chunk_image_link_create(
        link: ChunkImageLinkCreate | tuple[int, int] | dict[str, Any],
    ) -> ChunkImageLinkCreate:
        if isinstance(link, ChunkImageLinkCreate):
            return link
        if isinstance(link, tuple):
            return ChunkImageLinkCreate(chunk_index=link[0], image_index=link[1])
        return ChunkImageLinkCreate(
            chunk_index=link["chunk_index"],
            image_index=link["image_index"],
        )

    async def _store_chunks(
        self,
        session: AsyncSession,
        document_id: UUID,
        chunks: Sequence[ChunkCreate],
    ) -> list[Chunk]:
        stored_chunks = [
            Chunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text=chunk.text,
                embedding=list(chunk.embedding),
                metadata_json=chunk.metadata,
            )
            for chunk in chunks
        ]
        session.add_all(stored_chunks)
        await session.flush()
        return stored_chunks

    async def _store_images(
        self,
        session: AsyncSession,
        document_id: UUID,
        images: Sequence[ImageCreate],
    ) -> list[Image]:
        stored_images = [
            Image(
                document_id=document_id,
                blob_path=image.blob_path,
                blob_url=image.blob_url,
                source_page=image.source_page,
                width=image.width,
                height=image.height,
                format=image.image_format,
                bbox_json=image.bbox,
                metadata_json=image.metadata,
            )
            for image in images
        ]
        session.add_all(stored_images)
        await session.flush()
        return stored_images

    async def _link_chunk_images_by_index(
        self,
        session: AsyncSession,
        chunks: Sequence[Chunk],
        images: Sequence[Image],
        chunk_image_links: Sequence[ChunkImageLinkCreate],
    ) -> list[ChunkImage]:
        stored_links = [
            ChunkImage(
                chunk_id=chunks[link.chunk_index].id,
                image_id=images[link.image_index].id,
            )
            for link in chunk_image_links
        ]
        session.add_all(stored_links)
        await session.flush()
        return stored_links

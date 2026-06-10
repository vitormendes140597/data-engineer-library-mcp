"""SQLAlchemy models for RAG persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src import config as app_config

DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_PROCESSING = "processing"
DOCUMENT_STATUS_COMPLETED = "completed"
DOCUMENT_STATUS_FAILED = "failed"
DOCUMENT_STATUS_DELETED = "deleted"

FAILURE_STATUS_PENDING = "pending"
FAILURE_STATUS_CLAIMED = "claimed"
FAILURE_STATUS_RESOLVED = "resolved"
FAILURE_STATUS_PERMANENTLY_FAILED = "permanently_failed"


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for persistence models."""


class Document(Base):
    """Source PDF document tracked by blob URL."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("blob_url", name="uq_documents_blob_url"),)

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    blob_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_length: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    etag: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.String(length=50),
        nullable=False,
        default=DOCUMENT_STATUS_PENDING,
        server_default=DOCUMENT_STATUS_PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.func.now(),
    )
    failure_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    images: Mapped[list[Image]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Chunk(Base):
    """Chunked document text with vector embedding."""

    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_document_id_chunk_index", "document_id", "chunk_index"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(app_config.VECTOR_DIMENSION), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
    chunk_images: Mapped[list[ChunkImage]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Image(Base):
    """Extracted image metadata stored for a document."""

    __tablename__ = "images"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    blob_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    blob_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_page: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer)
    height: Mapped[int | None] = mapped_column(sa.Integer)
    format: Mapped[str | None] = mapped_column(sa.String(length=32))
    bbox_json: Mapped[Any | None] = mapped_column("bbox", sa.JSON)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="images")
    chunk_images: Mapped[list[ChunkImage]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChunkImage(Base):
    """Association between chunks and extracted images."""

    __tablename__ = "chunk_images"
    __table_args__ = (
        Index("ix_chunk_images_chunk_id_image_id", "chunk_id", "image_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chunk_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
    )

    chunk: Mapped[Chunk] = relationship(back_populates="chunk_images")
    image: Mapped[Image] = relationship(back_populates="chunk_images")


class ProcessingFailure(Base):
    """Durable processing failure record for scheduled retries."""

    __tablename__ = "processing_failures"
    __table_args__ = (
        Index("ix_processing_failures_status_next_retry_at", "status", "next_retry_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    blob_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    event_payload: Mapped[Any] = mapped_column(sa.JSON, nullable=False)
    failure_stage: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    error_message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    error_traceback: Mapped[str] = mapped_column(sa.Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1,
        server_default=sa.text("1"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(length=50),
        nullable=False,
        default=FAILURE_STATUS_PENDING,
        server_default=FAILURE_STATUS_PENDING,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.func.now(),
    )

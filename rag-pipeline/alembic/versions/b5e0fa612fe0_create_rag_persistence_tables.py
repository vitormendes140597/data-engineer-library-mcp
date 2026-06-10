"""create rag persistence tables

Revision ID: b5e0fa612fe0
Revises: 94467f2afd6c
Create Date: 2026-06-03 19:39:39.258079

"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from src import config as app_config

# revision identifiers, used by Alembic.
revision = "b5e0fa612fe0"
down_revision = "94467f2afd6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("content_length", sa.BigInteger(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blob_url", name="uq_documents_blob_url"),
    )
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(app_config.VECTOR_DIMENSION), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_path", sa.Text(), nullable=False),
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("format", sa.String(length=32), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "chunk_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "processing_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("failure_stage", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_chunks_document_id_chunk_index",
        "chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_chunk_images_chunk_id_image_id",
        "chunk_images",
        ["chunk_id", "image_id"],
        unique=False,
    )
    op.create_index(
        "ix_processing_failures_status_next_retry_at",
        "processing_failures",
        ["status", "next_retry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processing_failures_status_next_retry_at", table_name="processing_failures"
    )
    op.drop_index("ix_chunk_images_chunk_id_image_id", table_name="chunk_images")
    op.drop_index(
        "ix_chunks_embedding_hnsw", table_name="chunks", postgresql_using="hnsw"
    )
    op.drop_index("ix_chunks_document_id_chunk_index", table_name="chunks")

    op.drop_table("processing_failures")
    op.drop_table("chunk_images")
    op.drop_table("images")
    op.drop_table("chunks")
    op.drop_table("documents")

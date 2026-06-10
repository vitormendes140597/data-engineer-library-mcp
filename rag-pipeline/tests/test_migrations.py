"""Integration tests for Alembic migrations against PostgreSQL pgvector."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_creates_expected_tables_columns_and_indexes(
    migrated_database_url: str,
) -> None:
    engine = create_engine(migrated_database_url)
    inspector = inspect(engine)

    try:
        tables = set(inspector.get_table_names())
        assert {
            "documents",
            "chunks",
            "images",
            "chunk_images",
            "processing_failures",
            "alembic_version",
        }.issubset(tables)

        document_columns = {column["name"] for column in inspector.get_columns("documents")}
        chunk_columns = {column["name"] for column in inspector.get_columns("chunks")}
        image_columns = {column["name"] for column in inspector.get_columns("images")}
        failure_columns = {
            column["name"] for column in inspector.get_columns("processing_failures")
        }

        assert {"id", "blob_url", "content_length", "etag", "status"}.issubset(
            document_columns
        )
        assert {
            "document_id",
            "chunk_index",
            "page_start",
            "page_end",
            "text",
            "embedding",
            "metadata",
        }.issubset(chunk_columns)
        assert {
            "document_id",
            "blob_path",
            "blob_url",
            "source_page",
            "format",
        }.issubset(image_columns)
        assert {
            "blob_url",
            "event_payload",
            "failure_stage",
            "attempt_count",
            "status",
            "next_retry_at",
            "error_traceback",
        }.issubset(failure_columns)

        unique_constraints = inspector.get_unique_constraints("documents")
        assert any(
            constraint["name"] == "uq_documents_blob_url"
            for constraint in unique_constraints
        )

        chunk_indexes = {index["name"] for index in inspector.get_indexes("chunks")}
        chunk_image_indexes = {
            index["name"] for index in inspector.get_indexes("chunk_images")
        }
        failure_indexes = {
            index["name"] for index in inspector.get_indexes("processing_failures")
        }

        assert "ix_chunks_document_id_chunk_index" in chunk_indexes
        assert "ix_chunks_embedding_hnsw" in chunk_indexes
        assert "ix_chunk_images_chunk_id_image_id" in chunk_image_indexes
        assert "ix_processing_failures_status_next_retry_at" in failure_indexes

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one() == "vector"
            assert connection.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'chunks' AND indexname = 'ix_chunks_embedding_hnsw'"
                )
            ).scalar_one()
    finally:
        engine.dispose()

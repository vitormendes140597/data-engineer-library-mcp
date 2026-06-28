"""Unit tests for Phase 6 failure handling and reprocessing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config import (
    AzureIdentityConfig,
    ChunkingConfig,
    DatabaseConfig,
    EmbeddingConfig,
    QueueConfig,
    RAGConfig,
    RetryConfig,
    StorageConfig,
)
from src.events.handlers import EventHandler
from src.events.parser import EventParser
from src.ingestion_worker import process_message
from src.persistence.models import DOCUMENT_STATUS_COMPLETED
from src.reprocessing.reprocessor import (
    ProcessingStageError,
    calculate_next_retry_at,
    process_blob,
    retry_processing,
)
from src.reprocessing.scheduler import process_due_failures


class _FakeQueueClient:
    def __init__(self, content: str) -> None:
        self.deleted_messages: list[tuple[str, str]] = []
        self._messages = [
            SimpleNamespace(id="message-1", content=content, pop_receipt="receipt-1")
        ]

    async def receive_messages(self):
        return self._messages

    async def delete_message(self, message_id: str, pop_receipt: str) -> None:
        self.deleted_messages.append((message_id, pop_receipt))


class _FakeRepository:
    def __init__(self) -> None:
        self.record_failure = AsyncMock(return_value="failure-1")
        self.mark_failure_resolved = AsyncMock()
        self.mark_failure_permanently_failed = AsyncMock()
        self.reschedule_failure = AsyncMock()
        self.get_due_pending_failures = AsyncMock(return_value=[])
        self.claim_failure = AsyncMock(return_value=True)
        self.get_document_by_blob_url = AsyncMock(return_value=None)


class _RecordingRepository(_FakeRepository):
    def __init__(self) -> None:
        super().__init__()
        self.replace_document_contents = AsyncMock(
            return_value=SimpleNamespace(replaced_image_paths=[])
        )


def _build_config() -> RAGConfig:
    return RAGConfig(
        queue=QueueConfig(AZURE_STORAGE_QUEUE_CONN_STR="UseDevelopmentStorage=true"),
        storage=StorageConfig(AZURE_STORAGE_BLOB_CONN_STR="UseDevelopmentStorage=true"),
        database=DatabaseConfig(
            DATABASE_URL="postgresql+psycopg://user:pass@localhost/db"
        ),
        embedding=EmbeddingConfig(provider="fake", fake_dimension=4),
        chunking=ChunkingConfig(),
        retry=RetryConfig(
            max_attempts=3, initial_delay_seconds=10, max_delay_seconds=40
        ),
        azure_identity=AzureIdentityConfig(),
    )


def _blob_created_payload() -> dict[str, object]:
    return {
        "id": "event-1",
        "eventType": "Microsoft.Storage.BlobCreated",
        "subject": "/blobServices/default/containers/raw-pdfs/blobs/sample.pdf",
        "eventTime": "2026-01-01T00:00:00Z",
        "data": {
            "url": "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/sample.pdf",
            "contentLength": 123,
            "eTag": '"etag-1"',
        },
    }


@pytest.mark.asyncio
async def test_process_message_records_failure_before_delete() -> None:
    queue_client = _FakeQueueClient(json.dumps(_blob_created_payload()))
    repository = _FakeRepository()
    event_handler = EventHandler(
        repository=repository,
        blob_client=SimpleNamespace(),
        reingest_document=AsyncMock(
            side_effect=ProcessingStageError("embedding", "embedding failed")
        ),
    )

    handled = await process_message(
        queue_client,
        EventParser(),
        event_handler,
        repository,
    )

    assert handled is True
    repository.record_failure.assert_awaited_once()
    assert repository.record_failure.await_args.kwargs["failure_stage"] == "embedding"
    assert queue_client.deleted_messages == [("message-1", "receipt-1")]


@pytest.mark.asyncio
async def test_retry_processing_reschedules_when_attempts_remain(monkeypatch) -> None:
    repository = _FakeRepository()
    blob_client = SimpleNamespace()
    config = _build_config()

    async def _raise_failure(*_args, **_kwargs):
        raise ProcessingStageError("download", "download failed")

    monkeypatch.setattr("src.reprocessing.reprocessor.process_blob", _raise_failure)

    success = await retry_processing(
        {
            "id": "failure-1",
            "blob_url": _blob_created_payload()["data"]["url"],
            "event_payload": _blob_created_payload(),
            "failure_stage": "download",
            "attempt_count": 1,
        },
        config,
        repository=repository,
        blob_client=blob_client,
    )

    assert success is False
    repository.reschedule_failure.assert_awaited_once()
    args = repository.reschedule_failure.await_args.args
    assert args[0] == "failure-1"
    assert args[2] == 2
    next_retry_at = args[1]
    assert next_retry_at > datetime.now(timezone.utc)
    assert next_retry_at <= datetime.now(timezone.utc) + timedelta(seconds=40)


@pytest.mark.asyncio
async def test_retry_processing_marks_permanent_failure_at_max_attempts(
    monkeypatch,
) -> None:
    repository = _FakeRepository()
    blob_client = SimpleNamespace()
    config = _build_config()

    async def _raise_failure(*_args, **_kwargs):
        raise ProcessingStageError("embedding", "embedding failed")

    monkeypatch.setattr("src.reprocessing.reprocessor.process_blob", _raise_failure)

    success = await retry_processing(
        {
            "id": "failure-1",
            "blob_url": _blob_created_payload()["data"]["url"],
            "event_payload": _blob_created_payload(),
            "failure_stage": "embedding",
            "attempt_count": 2,
        },
        config,
        repository=repository,
        blob_client=blob_client,
    )

    assert success is False
    repository.mark_failure_permanently_failed.assert_awaited_once_with("failure-1")
    repository.reschedule_failure.assert_not_called()


@pytest.mark.asyncio
async def test_process_due_failures_marks_successful_retries_resolved(
    monkeypatch,
) -> None:
    repository = _FakeRepository()
    blob_client = SimpleNamespace()
    config = _build_config()
    repository.get_due_pending_failures.return_value = [
        {
            "id": "failure-1",
            "blob_url": _blob_created_payload()["data"]["url"],
            "event_payload": _blob_created_payload(),
            "failure_stage": "download",
            "attempt_count": 1,
        }
    ]

    async def _succeed(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr("src.reprocessing.scheduler.retry_processing", _succeed)

    processed = await process_due_failures(repository, config, blob_client)

    assert processed == 1
    repository.claim_failure.assert_awaited_once_with("failure-1")
    repository.mark_failure_resolved.assert_awaited_once_with("failure-1")


@pytest.mark.asyncio
async def test_process_blob_skips_completed_duplicate(monkeypatch) -> None:
    repository = _FakeRepository()
    repository.get_document_by_blob_url.return_value = SimpleNamespace(
        id="document-1",
        content_length=123,
        status=DOCUMENT_STATUS_COMPLETED,
    )
    blob_client = SimpleNamespace()
    config = _build_config()

    async def _unexpected_download(*_args, **_kwargs):
        raise AssertionError("download should not be called")

    monkeypatch.setattr(
        "src.reprocessing.reprocessor.download_pdf", _unexpected_download
    )

    await process_blob(
        _blob_created_payload()["data"]["url"],
        123,
        '"etag-1"',
        config,
        repository,
        blob_client,
    )


@pytest.mark.asyncio
async def test_process_blob_persists_structured_chunk_metadata(
    monkeypatch,
    sample_pdf_bytes,
) -> None:
    repository = _RecordingRepository()
    blob_client = SimpleNamespace(delete_extracted_image_blobs=AsyncMock())
    config = _build_config()

    async def _download_pdf(*_args, **_kwargs):
        return sample_pdf_bytes

    async def _extract_images(*_args, **_kwargs):
        return []

    monkeypatch.setattr("src.reprocessing.reprocessor.download_pdf", _download_pdf)
    monkeypatch.setattr(
        "src.reprocessing.reprocessor.extract_and_upload_images", _extract_images
    )

    await process_blob(
        _blob_created_payload()["data"]["url"],
        len(sample_pdf_bytes),
        '"etag-1"',
        config,
        repository,
        blob_client,
    )

    chunks = repository.replace_document_contents.await_args.kwargs["chunks"]

    assert chunks
    assert chunks[0].metadata["page_range"] == [1, 1]
    assert "heading_path" in chunks[0].metadata
    assert "element_types" in chunks[0].metadata
    assert "source_elements" in chunks[0].metadata


@pytest.mark.asyncio
async def test_calculate_next_retry_at_uses_exponential_backoff() -> None:
    config = _build_config()

    next_retry_at = calculate_next_retry_at(config, 3)

    assert next_retry_at >= datetime.now(timezone.utc) + timedelta(seconds=39)

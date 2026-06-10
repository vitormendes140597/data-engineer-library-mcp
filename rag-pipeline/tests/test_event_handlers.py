"""Unit tests for event handler decisions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.events.handlers import EventHandler
from src.events.parser import EventParser


@pytest.fixture
def parser() -> EventParser:
    return EventParser()


@pytest.fixture
def repository() -> SimpleNamespace:
    return SimpleNamespace(
        get_document_by_blob_url=AsyncMock(return_value=None),
        delete_document_content=AsyncMock(return_value=[]),
    )


@pytest.fixture
def blob_client() -> SimpleNamespace:
    return SimpleNamespace(delete_extracted_image_blobs=AsyncMock())


@pytest.fixture
def reingest_document() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(
    repository: SimpleNamespace,
    blob_client: SimpleNamespace,
    reingest_document: AsyncMock,
) -> EventHandler:
    return EventHandler(
        repository=repository,
        blob_client=blob_client,
        reingest_document=reingest_document,
    )


@pytest.mark.asyncio
async def test_blob_created_for_new_document_proceeds_with_ingestion(
    handler: EventHandler,
    repository: SimpleNamespace,
    reingest_document: AsyncMock,
    blob_created_payload: dict[str, object],
    parser: EventParser,
) -> None:
    event = parser.parse(blob_created_payload)

    outcome = await handler.handle_blob_created(event)

    assert outcome == "ingested"
    assert repository.get_document_by_blob_url.await_count == 2
    repository.get_document_by_blob_url.assert_any_await(event.blob_url)
    reingest_document.assert_awaited_once_with(
        event.blob_url, event.content_length, event.etag
    )
    repository.delete_document_content.assert_not_called()


@pytest.mark.asyncio
async def test_blob_created_for_same_size_document_skips_processing(
    handler: EventHandler,
    repository: SimpleNamespace,
    reingest_document: AsyncMock,
    blob_created_payload: dict[str, object],
    parser: EventParser,
) -> None:
    event = parser.parse(blob_created_payload)
    repository.get_document_by_blob_url.return_value = SimpleNamespace(content_length=123)

    outcome = await handler.handle_blob_created(event)

    assert outcome == "skipped"
    reingest_document.assert_not_called()
    repository.delete_document_content.assert_not_called()


@pytest.mark.asyncio
async def test_blob_created_for_changed_size_document_replaces_before_reingesting(
    handler: EventHandler,
    repository: SimpleNamespace,
    reingest_document: AsyncMock,
    blob_created_payload: dict[str, object],
    parser: EventParser,
) -> None:
    event = parser.parse(blob_created_payload)
    repository.get_document_by_blob_url.side_effect = [
        SimpleNamespace(content_length=999),
        SimpleNamespace(content_length=999),
    ]
    call_order: list[str] = []

    async def delete_document_content(blob_url: str) -> list[str]:
        call_order.append(f"delete:{blob_url}")
        return ["images/old.png"]

    async def trigger_reingestion(blob_url: str, content_length: int | None, etag: str | None) -> None:
        call_order.append(f"reingest:{blob_url}:{content_length}:{etag}")

    repository.delete_document_content.side_effect = delete_document_content
    reingest_document.side_effect = trigger_reingestion

    outcome = await handler.handle_blob_created(event)

    assert outcome == "replaced"
    assert call_order == [
        f"delete:{event.blob_url}",
        f"reingest:{event.blob_url}:{event.content_length}:{event.etag}",
    ]


@pytest.mark.asyncio
async def test_blob_deleted_for_known_document_triggers_cleanup(
    handler: EventHandler,
    repository: SimpleNamespace,
    blob_deleted_payload: dict[str, object],
    parser: EventParser,
) -> None:
    event = parser.parse(blob_deleted_payload)
    repository.delete_document_content.return_value = [
        "chunks-removed",
        "images-removed",
        "vectors-removed",
        "blob-path/image.png",
    ]

    outcome = await handler.handle_event(event)

    assert outcome == "deleted"
    repository.delete_document_content.assert_awaited_once_with(event.blob_url)


@pytest.mark.asyncio
async def test_blob_deleted_for_unknown_document_is_graceful_noop(
    handler: EventHandler,
    repository: SimpleNamespace,
    blob_deleted_payload: dict[str, object],
    parser: EventParser,
) -> None:
    event = parser.parse(blob_deleted_payload)
    repository.delete_document_content.return_value = []

    deleted_paths = await handler.handle_blob_deleted(event.blob_url)

    assert deleted_paths == []
    repository.delete_document_content.assert_awaited_once_with(event.blob_url)

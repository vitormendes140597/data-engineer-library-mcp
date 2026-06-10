"""Event routing and storage cleanup handlers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from src.blob.client import BlobClient
from src.events.parser import EventData
from src.persistence.repository import Repository

logger = logging.getLogger(__name__)

ReingestCallback = Callable[[str, int | None, str | None], Awaitable[None]]


class EventHandler:
    """Handle blob lifecycle events using repository and blob storage clients."""

    def __init__(
        self,
        repository: Repository,
        blob_client: BlobClient,
        reingest_document: ReingestCallback | None = None,
    ):
        self._repository = repository
        self._blob_client = blob_client
        self._reingest_document = reingest_document

    async def check_document_exists(
        self, blob_url: str, content_length: int | None
    ) -> bool:
        """Return True when an existing document matches the incoming content size."""
        if content_length is None:
            return False

        document = await self._repository.get_document_by_blob_url(blob_url)
        return document is not None and document.content_length == content_length

    async def handle_blob_created(self, event: EventData) -> str:
        """Handle BlobCreated events with skip or replacement semantics."""
        if await self.check_document_exists(event.blob_url, event.content_length):
            logger.info(
                "Skipping blob %s because content length %s already exists",
                event.blob_url,
                event.content_length,
            )
            return "skipped"

        existing_document = await self._repository.get_document_by_blob_url(
            event.blob_url
        )
        if existing_document is not None:
            await self.handle_blob_replaced(
                event.blob_url,
                event.content_length,
                event.etag,
            )
            return "replaced"

        await self._trigger_reingestion(
            event.blob_url, event.content_length, event.etag
        )
        return "ingested"

    async def handle_blob_replaced(
        self,
        blob_url: str,
        content_length: int | None,
        etag: str | None,
    ) -> list[str]:
        """Delete previous document content and trigger re-ingestion."""
        replaced_image_paths = await self._repository.delete_document_content(blob_url)
        await self._trigger_reingestion(blob_url, content_length, etag)
        return replaced_image_paths

    async def handle_blob_deleted(self, blob_url: str) -> list[str]:
        """Remove document rows and extracted image blobs for a deleted source PDF."""
        return await self._repository.delete_document_content(blob_url)

    async def handle_event(self, event: EventData) -> str:
        """Route a parsed event to the appropriate handler."""
        if event.event_type == "Microsoft.Storage.BlobCreated":
            return await self.handle_blob_created(event)
        if event.event_type == "Microsoft.Storage.BlobDeleted":
            await self.handle_blob_deleted(event.blob_url)
            return "deleted"
        raise ValueError(f"Unsupported event type: {event.event_type}")

    async def _trigger_reingestion(
        self,
        blob_url: str,
        content_length: int | None,
        etag: str | None,
    ) -> None:
        if self._reingest_document is None:
            logger.info(
                "Queued blob %s for downstream PDF extraction (content_length=%s)",
                blob_url,
                content_length,
            )
            return

        await self._reingest_document(blob_url, content_length, etag)

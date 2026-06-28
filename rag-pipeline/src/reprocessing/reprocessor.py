"""Blob reprocessing and retry helpers."""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.blob.client import BlobClient
from src.chunking.chunker import chunk_elements
from src.chunking.image_linking import link_chunks_to_images
from src.config import RAGConfig
from src.embeddings.batcher import batch_embed
from src.embeddings.provider import get_embedding_provider
from src.events.parser import EventParser
from src.extraction.downloader import download_pdf
from src.extraction.image_extractor import extract_and_upload_images
from src.extraction.pdf_parser import extract_structure
from src.persistence.models import DOCUMENT_STATUS_COMPLETED
from src.persistence.repository import (
    ChunkCreate,
    ChunkImageLinkCreate,
    DocumentCreate,
    ImageCreate,
    Repository,
)

logger = logging.getLogger(__name__)

FAILURE_STAGE_DOWNLOAD = "download"
FAILURE_STAGE_EXTRACTION = "extraction"
FAILURE_STAGE_CHUNKING = "chunking"
FAILURE_STAGE_EMBEDDING = "embedding"
FAILURE_STAGE_PERSISTENCE = "persistence"


class ProcessingStageError(RuntimeError):
    """Wrap processing failures with the stage that raised them."""

    def __init__(self, failure_stage: str, message: str):
        super().__init__(message)
        self.failure_stage = failure_stage


async def process_blob(
    blob_url: str,
    content_length: int | None,
    etag: str | None,
    config: RAGConfig,
    repository: Repository,
    blob_client: BlobClient,
) -> None:
    """Download, extract, embed, and persist one blob idempotently."""
    existing_document = await repository.get_document_by_blob_url(blob_url)
    if (
        existing_document is not None
        and content_length is not None
        and existing_document.content_length == content_length
        and existing_document.status == DOCUMENT_STATUS_COMPLETED
    ):
        logger.info(
            "Blob %s is already processed with matching content length", blob_url
        )
        return

    document_id = (
        str(existing_document.id)
        if existing_document is not None
        else str(uuid5(NAMESPACE_URL, blob_url))
    )
    uploaded_image_paths: list[str] = []
    embedding_provider = get_embedding_provider(config.embedding)

    try:
        try:
            pdf_bytes = await download_pdf(blob_url, config)
        except Exception as exc:  # pragma: no cover - exercised by higher-level tests
            raise ProcessingStageError(
                FAILURE_STAGE_DOWNLOAD, f"Failed to download PDF from {blob_url}: {exc}"
            ) from exc

        try:
            extraction_result = await extract_structure(pdf_bytes)
            images = await extract_and_upload_images(
                pdf_bytes,
                document_id=document_id,
                blob_client=blob_client,
                config=config,
            )
            uploaded_image_paths = [image["blob_path"] for image in images]
        except Exception as exc:
            raise ProcessingStageError(
                FAILURE_STAGE_EXTRACTION,
                f"Failed to extract markdown or images from {blob_url}: {exc}",
            ) from exc

        try:
            chunks = await chunk_elements(extraction_result.elements, config.chunking)
            links = await link_chunks_to_images(chunks, images)
        except Exception as exc:
            await _cleanup_uploaded_images(blob_client, uploaded_image_paths)
            raise ProcessingStageError(
                FAILURE_STAGE_CHUNKING,
                f"Failed to chunk extracted content for {blob_url}: {exc}",
            ) from exc

        try:
            embeddings = await batch_embed(
                [str(chunk["text"]) for chunk in chunks],
                embedding_provider,
                config.embedding,
            )
        except Exception as exc:
            await _cleanup_uploaded_images(blob_client, uploaded_image_paths)
            raise ProcessingStageError(
                FAILURE_STAGE_EMBEDDING,
                f"Failed to embed extracted content for {blob_url}: {exc}",
            ) from exc

        chunk_payloads = [
            ChunkCreate(
                chunk_index=int(chunk["chunk_index"]),
                page_start=int(chunk["page_start"]),
                page_end=int(chunk["page_end"]),
                text=str(chunk["text"]),
                embedding=embedding,
                metadata=dict(chunk.get("metadata", {})),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=False)
        ]
        image_payloads = [
            ImageCreate(
                blob_path=str(image["blob_path"]),
                blob_url=str(image["blob_url"]),
                source_page=int(image["source_page"]),
                width=_coerce_optional_int(image.get("width")),
                height=_coerce_optional_int(image.get("height")),
                image_format=_coerce_optional_str(image.get("format")),
                bbox=image.get("bbox"),
                metadata=dict(image.get("metadata", {})),
            )
            for image in images
        ]
        chunk_image_links = [
            ChunkImageLinkCreate(chunk_index=chunk_index, image_index=image_index)
            for chunk_index, image_index in links
        ]

        try:
            replacement = await repository.replace_document_contents(
                DocumentCreate(
                    blob_url=blob_url,
                    content_length=content_length or len(pdf_bytes),
                    etag=etag,
                    status=DOCUMENT_STATUS_COMPLETED,
                    failure_count=0,
                ),
                chunks=chunk_payloads,
                images=image_payloads,
                chunk_image_links=chunk_image_links,
            )
        except Exception as exc:
            await _cleanup_uploaded_images(blob_client, uploaded_image_paths)
            raise ProcessingStageError(
                FAILURE_STAGE_PERSISTENCE,
                f"Failed to persist extracted content for {blob_url}: {exc}",
            ) from exc

        if replacement.replaced_image_paths:
            await blob_client.delete_extracted_image_blobs(
                replacement.replaced_image_paths
            )
    finally:
        await embedding_provider.close()


async def retry_processing(
    failure: dict[str, Any],
    config: RAGConfig,
    *,
    repository: Repository,
    blob_client: BlobClient,
) -> bool:
    """Retry one failed PDF processing record."""
    attempt_count = int(failure["attempt_count"])
    logger.info(
        "Retrying failure %s for blob %s at stage %s (attempt %s/%s)",
        failure["id"],
        failure["blob_url"],
        failure["failure_stage"],
        attempt_count,
        config.retry.max_attempts,
    )

    parser = EventParser()
    payload = failure["event_payload"]
    event = parser.parse(payload)

    try:
        await process_blob(
            blob_url=failure["blob_url"],
            content_length=event.content_length,
            etag=event.etag,
            config=config,
            repository=repository,
            blob_client=blob_client,
        )
        logger.info(
            "Resolved failure %s for blob %s", failure["id"], failure["blob_url"]
        )
        return True
    except Exception as exc:
        updated_attempt_count = attempt_count + 1
        error_message = str(exc)
        error_traceback = traceback.format_exc()

        if updated_attempt_count >= config.retry.max_attempts:
            logger.warning(
                "Failure %s reached max attempts (%s); marking permanently failed",
                failure["id"],
                updated_attempt_count,
            )
            await repository.mark_failure_permanently_failed(failure["id"])
            return False

        next_retry_at = calculate_next_retry_at(config, updated_attempt_count)
        logger.warning(
            "Retry failed for %s (attempt %s/%s). Rescheduling for %s",
            failure["id"],
            updated_attempt_count,
            config.retry.max_attempts,
            next_retry_at.isoformat(),
        )
        await repository.reschedule_failure(
            failure["id"],
            next_retry_at,
            updated_attempt_count,
            error_message=error_message,
            error_traceback=error_traceback,
        )
        return False


def calculate_next_retry_at(config: RAGConfig, attempt_count: int) -> datetime:
    """Calculate the next retry timestamp using exponential backoff."""
    delay_seconds = min(
        config.retry.initial_delay_seconds * (2 ** max(attempt_count - 1, 0)),
        config.retry.max_delay_seconds,
    )
    return datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)


async def _cleanup_uploaded_images(
    blob_client: BlobClient,
    uploaded_image_paths: list[str],
) -> None:
    if not uploaded_image_paths:
        return
    await blob_client.delete_extracted_image_blobs(uploaded_image_paths)


def _coerce_optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _coerce_optional_str(value: Any) -> str | None:
    return None if value is None else str(value)

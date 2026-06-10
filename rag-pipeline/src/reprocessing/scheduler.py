"""Scheduled failure selection and processing helpers."""

from __future__ import annotations

import logging

from src.blob.client import BlobClient
from src.config import RAGConfig
from src.persistence.repository import Repository
from src.reprocessing.reprocessor import retry_processing

logger = logging.getLogger(__name__)


async def process_due_failures(
    repository: Repository,
    config: RAGConfig,
    blob_client: BlobClient,
) -> int:
    """Claim and process all due pending failures for this execution."""
    due_failures = await repository.get_due_pending_failures()
    logger.info("Found %s due pending failures", len(due_failures))

    processed = 0
    for failure in due_failures:
        try:
            claimed = await repository.claim_failure(failure["id"])
            if not claimed:
                logger.info("Skipping already-claimed failure %s", failure["id"])
                continue

            processed += 1
            succeeded = await retry_processing(
                failure,
                config,
                repository=repository,
                blob_client=blob_client,
            )
            if succeeded:
                await repository.mark_failure_resolved(failure["id"])
        except Exception as exc:  # pragma: no cover - defensive scheduling guard
            logger.exception("Failed to process failure %s: %s", failure["id"], exc)

    return processed

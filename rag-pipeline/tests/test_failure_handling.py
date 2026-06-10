"""Unit tests for failure state transitions and retry behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from src.persistence.models import (
    FAILURE_STATUS_CLAIMED,
    FAILURE_STATUS_PENDING,
    FAILURE_STATUS_PERMANENTLY_FAILED,
    FAILURE_STATUS_RESOLVED,
    ProcessingFailure,
)
from src.reprocessing.reprocessor import calculate_next_retry_at, retry_processing


async def _get_failure_row(repository: object, failure_id: str) -> ProcessingFailure:
    async with repository._session_factory() as session:  # noqa: SLF001
        result = await session.execute(
            select(ProcessingFailure).where(ProcessingFailure.id == UUID(failure_id))
        )
        return result.scalar_one()


@pytest.mark.asyncio
async def test_record_failure_creates_pending_row_with_attempt_count_one(
    repository: object, blob_created_payload: dict[str, object], rag_config: object
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="download",
        error_message="download failed",
        error_traceback="traceback",
    )

    failure = await _get_failure_row(repository, failure_id)

    assert failure.status == FAILURE_STATUS_PENDING
    assert failure.attempt_count == 1
    assert failure.next_retry_at > datetime.now(timezone.utc)
    assert failure.next_retry_at <= datetime.now(timezone.utc) + timedelta(
        seconds=rag_config.retry.initial_delay_seconds + 1
    )


@pytest.mark.asyncio
async def test_claim_failure_transitions_pending_to_claimed_once(
    repository: object, blob_created_payload: dict[str, object]
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="embedding",
        error_message="embedding failed",
        error_traceback="traceback",
    )

    assert await repository.claim_failure(failure_id) is True
    assert await repository.claim_failure(failure_id) is False

    failure = await _get_failure_row(repository, failure_id)
    assert failure.status == FAILURE_STATUS_CLAIMED


@pytest.mark.asyncio
async def test_mark_failure_resolved_sets_status_resolved(
    repository: object, blob_created_payload: dict[str, object]
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="chunking",
        error_message="chunking failed",
        error_traceback="traceback",
    )

    await repository.mark_failure_resolved(failure_id)

    failure = await _get_failure_row(repository, failure_id)
    assert failure.status == FAILURE_STATUS_RESOLVED


@pytest.mark.asyncio
async def test_retry_processing_reschedules_when_attempts_remain(
    repository: object,
    rag_config: object,
    blob_created_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="download",
        error_message="download failed",
        error_traceback="traceback",
    )
    await repository.claim_failure(failure_id)

    async def raise_failure(*_args, **_kwargs) -> None:
        raise RuntimeError("download failed again")

    monkeypatch.setattr("src.reprocessing.reprocessor.process_blob", raise_failure)

    succeeded = await retry_processing(
        {
            "id": failure_id,
            "blob_url": blob_created_payload["data"]["url"],
            "event_payload": blob_created_payload,
            "failure_stage": "download",
            "attempt_count": 1,
        },
        rag_config,
        repository=repository,
        blob_client=SimpleNamespace(),
    )

    assert succeeded is False
    failure = await _get_failure_row(repository, failure_id)
    assert failure.status == FAILURE_STATUS_PENDING
    assert failure.attempt_count == 2
    assert "download failed again" in failure.error_message


@pytest.mark.asyncio
async def test_retry_processing_marks_permanently_failed_at_max_attempts(
    repository: object,
    rag_config: object,
    blob_created_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="embedding",
        error_message="embedding failed",
        error_traceback="traceback",
    )
    await repository.claim_failure(failure_id)
    await repository.reschedule_failure(
        failure_id,
        datetime.now(timezone.utc),
        attempt_count=2,
    )
    await repository.claim_failure(failure_id)

    async def raise_failure(*_args, **_kwargs) -> None:
        raise RuntimeError("embedding failed again")

    monkeypatch.setattr("src.reprocessing.reprocessor.process_blob", raise_failure)

    succeeded = await retry_processing(
        {
            "id": failure_id,
            "blob_url": blob_created_payload["data"]["url"],
            "event_payload": blob_created_payload,
            "failure_stage": "embedding",
            "attempt_count": 2,
        },
        rag_config,
        repository=repository,
        blob_client=SimpleNamespace(),
    )

    assert succeeded is False
    failure = await _get_failure_row(repository, failure_id)
    assert failure.status == FAILURE_STATUS_PERMANENTLY_FAILED
    assert failure.attempt_count == 2


@pytest.mark.asyncio
async def test_calculate_next_retry_at_uses_exponential_backoff(
    rag_config: object,
) -> None:
    next_retry_at = calculate_next_retry_at(rag_config, 3)
    delay = (next_retry_at - datetime.now(timezone.utc)).total_seconds()

    assert 19 <= delay <= 21


@pytest.mark.asyncio
async def test_concurrent_claim_attempts_only_allow_one_winner(
    repository: object, blob_created_payload: dict[str, object]
) -> None:
    failure_id = await repository.record_failure(
        blob_url=blob_created_payload["data"]["url"],
        event_payload=blob_created_payload,
        failure_stage="persistence",
        error_message="persistence failed",
        error_traceback="traceback",
    )

    first, second = await asyncio.gather(
        repository.claim_failure(failure_id),
        repository.claim_failure(failure_id),
    )

    assert sorted([first, second]) == [False, True]

"""RAG pipeline ingestion worker entrypoint."""

import asyncio
import json
import logging
import sys
import traceback
from typing import Any

from src.blob.client import BlobClient
from src.config import RAGConfig
from src.events.handlers import EventHandler
from src.events.parser import EventData, EventParser
from src.persistence.repository import Repository
from src.queue.client import QueueClient
from src.reprocessing.reprocessor import ProcessingStageError, process_blob

logger = logging.getLogger(__name__)


async def process_message(
    queue_client: QueueClient,
    event_parser: EventParser,
    event_handler: EventHandler,
    repository: Repository,
) -> bool:
    """Receive one message, route it, and delete it after handling."""
    messages = await queue_client.receive_messages()
    if not messages:
        logger.info("No messages in queue, exiting.")
        return False

    message = messages[0]
    logger.info("Processing message %s", message.id)

    event: EventData | None = None
    payload: Any = message.content
    try:
        payload = _deserialize_event_payload(message.content)
        event = event_parser.parse(payload)
        outcome = await event_handler.handle_event(event)
        logger.info("Event %s handled with outcome=%s", event.event_type, outcome)
        await queue_client.delete_message(message.id, message.pop_receipt)
        return True
    except Exception as exc:
        logger.exception("Error processing message %s: %s", message.id, exc)
        if event is not None and event.event_type == "Microsoft.Storage.BlobCreated":
            failure_stage = _resolve_failure_stage(exc)
            try:
                failure_id = await repository.record_failure(
                    blob_url=event.blob_url,
                    event_payload=payload,
                    failure_stage=failure_stage,
                    error_message=str(exc),
                    error_traceback=traceback.format_exc(),
                )
                logger.info(
                    "Recorded failure %s for blob %s at stage %s",
                    failure_id,
                    event.blob_url,
                    failure_stage,
                )
            except Exception as record_exc:
                logger.exception(
                    "Failed to record processing failure for message %s: %s",
                    message.id,
                    record_exc,
                )
        await queue_client.delete_message(message.id, message.pop_receipt)
        return True


async def main() -> None:
    """Main ingestion worker entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    queue_client: QueueClient | None = None
    blob_client: BlobClient | None = None
    repository: Repository | None = None

    try:
        config = RAGConfig.from_env()
        queue_client = QueueClient(config.queue)
        blob_client = BlobClient(config.storage)
        event_parser = EventParser()
        repository = Repository(
            config.database,
            blob_client=blob_client,
            retry_config=config.retry,
        )

        async def reingest_blob(
            blob_url: str,
            content_length: int | None,
            etag: str | None,
        ) -> None:
            await process_blob(
                blob_url=blob_url,
                content_length=content_length,
                etag=etag,
                config=config,
                repository=repository,
                blob_client=blob_client,
            )

        event_handler = EventHandler(
            repository=repository,
            blob_client=blob_client,
            reingest_document=reingest_blob,
        )

        await process_message(queue_client, event_parser, event_handler, repository)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)
    finally:
        if queue_client is not None:
            await queue_client.close()
        if blob_client is not None:
            await blob_client.close()
        if repository is not None:
            await repository.dispose()


def _deserialize_event_payload(message_content: str | bytes | dict | list[dict]) -> Any:
    if isinstance(message_content, (str, bytes, bytearray)):
        return json.loads(message_content)
    return message_content


def _resolve_failure_stage(exc: Exception) -> str:
    if isinstance(exc, ProcessingStageError):
        return exc.failure_stage
    return "persistence"


if __name__ == "__main__":
    asyncio.run(main())

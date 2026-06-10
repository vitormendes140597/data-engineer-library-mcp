"""Async Azure Storage Queue client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import QueueConfig


@dataclass(slots=True)
class QueueMessage:
    """Application queue message representation."""

    id: str
    content: str
    pop_receipt: str
    dequeue_count: int | None = None
    insertion_time: datetime | None = None
    expiration_time: datetime | None = None
    time_next_visible: datetime | None = None


class QueueClient:
    """Async Storage Queue operations used by the worker and local CLI."""

    def __init__(self, config: QueueConfig):
        from azure.storage.queue.aio import QueueClient as AzureQueueClient

        self._config = config
        self._client: Any = AzureQueueClient.from_connection_string(
            conn_str=config.connection_string,
            queue_name=config.queue_name,
        )

    async def receive_messages(self) -> list[QueueMessage]:
        """Receive at most one queue message using the configured visibility timeout."""
        max_messages = max(1, min(self._config.max_receive_messages, 1))
        received: list[QueueMessage] = []

        async for message in self._client.receive_messages(
            messages_per_page=max_messages,
            visibility_timeout=self._config.visibility_timeout,
        ):
            received.append(
                QueueMessage(
                    id=message.id,
                    content=message.content,
                    pop_receipt=message.pop_receipt,
                    dequeue_count=getattr(message, "dequeue_count", None),
                    insertion_time=getattr(message, "inserted_on", None),
                    expiration_time=getattr(message, "expires_on", None),
                    time_next_visible=getattr(message, "next_visible_on", None),
                )
            )
            break

        return received

    async def send_message(self, content: str) -> None:
        """Send a raw queue message."""
        await self._client.send_message(content)

    async def delete_message(self, message_id: str, pop_receipt: str) -> None:
        """Delete a queue message after processing completes."""
        await self._client.delete_message(message_id, pop_receipt=pop_receipt)

    async def update_message_visibility(
        self,
        message_id: str,
        pop_receipt: str,
        visibility_timeout: int,
    ) -> None:
        """Extend or shorten queue message invisibility."""
        await self._client.update_message(
            message_id,
            pop_receipt=pop_receipt,
            visibility_timeout=visibility_timeout,
        )

    async def close(self) -> None:
        """Close the underlying async SDK client."""
        await self._client.close()

    async def __aenter__(self) -> "QueueClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

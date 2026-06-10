"""Parse Event Grid queue messages into typed event objects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

SUPPORTED_EVENT_TYPES = {
    "Microsoft.Storage.BlobCreated",
    "Microsoft.Storage.BlobDeleted",
}


@dataclass(slots=True)
class BlobEventDetails:
    """Blob-specific Event Grid payload fields."""

    blob_url: str
    blob_name: str
    content_length: int | None = None
    etag: str | None = None
    blob_type: str | None = None

    @property
    def url(self) -> str:
        return self.blob_url

    @property
    def contentLength(self) -> int | None:
        return self.content_length

    @property
    def eTag(self) -> str | None:
        return self.etag

    @property
    def blobType(self) -> str | None:
        return self.blob_type


@dataclass(slots=True)
class EventData:
    """Typed Event Grid event consumed by the worker."""

    event_type: str
    subject: str
    data: BlobEventDetails
    event_id: str
    event_time: datetime

    @property
    def eventType(self) -> str:
        return self.event_type

    @property
    def id(self) -> str:
        return self.event_id

    @property
    def eventTime(self) -> datetime:
        return self.event_time

    @property
    def blob_url(self) -> str:
        return self.data.blob_url

    @property
    def blob_name(self) -> str:
        return self.data.blob_name

    @property
    def content_length(self) -> int | None:
        return self.data.content_length

    @property
    def etag(self) -> str | None:
        return self.data.etag


class EventParser:
    """Event Grid payload parser for queue-delivered storage events."""

    def parse(self, message_content: str | bytes | dict | list[dict]) -> EventData:
        """Parse a Storage Queue message into a typed EventData object."""
        payload = self._load_payload(message_content)
        event_type = payload.get("eventType") or payload.get("event_type")
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        data = payload.get("data") or {}
        blob_url = data.get("url")
        if not blob_url:
            raise ValueError("Event payload missing data.url")

        subject = payload.get("subject", "")
        return EventData(
            event_type=event_type,
            subject=subject,
            data=BlobEventDetails(
                blob_url=blob_url,
                blob_name=self._extract_blob_name(subject, blob_url),
                content_length=self._parse_optional_int(data.get("contentLength")),
                etag=data.get("eTag") or data.get("etag"),
                blob_type=data.get("blobType"),
            ),
            event_id=str(payload.get("id", "")),
            event_time=self._parse_event_time(payload.get("eventTime")),
        )

    def _load_payload(self, message_content: str | bytes | dict | list[dict]) -> dict:
        if isinstance(message_content, (str, bytes, bytearray)):
            payload = json.loads(message_content)
        else:
            payload = message_content

        if isinstance(payload, list):
            if not payload:
                raise ValueError("Queue message did not contain an event payload")
            payload = payload[0]

        if not isinstance(payload, dict):
            raise ValueError(
                "Queue message must contain a JSON object or single-item list"
            )

        return payload

    def _extract_blob_name(self, subject: str, blob_url: str) -> str:
        if "/blobs/" in subject:
            return unquote(subject.split("/blobs/", 1)[1])

        path_parts = [part for part in urlparse(blob_url).path.split("/") if part]
        if len(path_parts) >= 3 and path_parts[0] == "devstoreaccount1":
            return unquote("/".join(path_parts[2:]))
        if len(path_parts) >= 2:
            return unquote("/".join(path_parts[1:]))
        raise ValueError(f"Unable to determine blob name from URL: {blob_url}")

    def _parse_event_time(self, value: str | datetime | None) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if not value:
            raise ValueError("Event payload missing eventTime")
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def _parse_optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        return int(value)

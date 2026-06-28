"""Unit tests for Event Grid payload parsing."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.events.parser import EventParser


@pytest.fixture
def parser() -> EventParser:
    return EventParser()


@pytest.fixture
def blob_created_json(blob_created_payload: dict[str, object]) -> str:
    payload = dict(blob_created_payload)
    payload["data"] = dict(payload["data"], contentLength="456")
    return json.dumps([payload])


def test_parse_blob_created_extracts_expected_fields(
    parser: EventParser, blob_created_json: str
) -> None:
    event = parser.parse(blob_created_json)

    assert event.event_type == "Microsoft.Storage.BlobCreated"
    assert event.blob_url.endswith("/raw-pdfs/books/sample.pdf")
    assert event.blob_name == "books/sample.pdf"
    assert event.content_length == 456
    assert event.etag == '"etag-created-1"'
    assert event.event_id == "event-created-1"
    assert event.event_time == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert event.data.blob_type == "BlockBlob"
    assert event.data.url == event.blob_url
    assert event.data.contentLength == 456
    assert event.data.eTag == '"etag-created-1"'
    assert event.eventType == "Microsoft.Storage.BlobCreated"
    assert event.id == "event-created-1"
    assert event.eventTime == event.event_time


def test_parse_blob_deleted_extracts_expected_fields(
    parser: EventParser, blob_deleted_payload: dict[str, object]
) -> None:
    payload = dict(blob_deleted_payload)
    payload["subject"] = ""
    payload["eventTime"] = datetime(2026, 1, 2, 12, 0)

    event = parser.parse(payload)

    assert event.event_type == "Microsoft.Storage.BlobDeleted"
    assert event.blob_url == payload["data"]["url"]
    assert event.blob_name == "books/sample.pdf"
    assert event.content_length is None
    assert event.etag is None
    assert event.event_id == "event-deleted-1"
    assert event.event_time == datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


def test_parse_supports_standard_blob_urls_without_subject(parser: EventParser) -> None:
    event = parser.parse(
        {
            "id": "azure-event-1",
            "eventType": "Microsoft.Storage.BlobDeleted",
            "subject": "",
            "eventTime": datetime(2026, 1, 3, 8, 0, tzinfo=timezone.utc),
            "data": {
                "url": "https://acct.blob.core.windows.net/raw-pdfs/folder/file.pdf"
            },
        }
    )

    assert event.blob_name == "folder/file.pdf"
    assert event.event_time == datetime(2026, 1, 3, 8, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("message_content", "expected_exception", "message_fragment"),
    [
        ("{not-valid-json}", json.JSONDecodeError, ""),
        ([], ValueError, "Queue message did not contain an event payload"),
        (
            123,
            ValueError,
            "Queue message must contain a JSON object or single-item list",
        ),
    ],
)
def test_parse_rejects_malformed_payloads(
    parser: EventParser,
    message_content: object,
    expected_exception: type[Exception],
    message_fragment: str,
) -> None:
    with pytest.raises(expected_exception) as exc_info:
        parser.parse(message_content)

    if message_fragment:
        assert message_fragment in str(exc_info.value)


@pytest.mark.parametrize(
    ("payload", "message_fragment"),
    [
        (
            {
                "id": "event-unsupported",
                "eventType": "Microsoft.Storage.BlobRenamed",
                "subject": "/blobServices/default/containers/raw-pdfs/blobs/sample.pdf",
                "eventTime": "2026-01-01T00:00:00Z",
                "data": {
                    "url": "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/sample.pdf"
                },
            },
            "Unsupported event type",
        ),
        (
            {
                "id": "event-missing-url",
                "eventType": "Microsoft.Storage.BlobCreated",
                "subject": "/blobServices/default/containers/raw-pdfs/blobs/sample.pdf",
                "eventTime": "2026-01-01T00:00:00Z",
                "data": {},
            },
            "Event payload missing data.url",
        ),
        (
            {
                "id": "event-missing-time",
                "eventType": "Microsoft.Storage.BlobDeleted",
                "subject": "/blobServices/default/containers/raw-pdfs/blobs/sample.pdf",
                "data": {
                    "url": "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/sample.pdf"
                },
            },
            "Event payload missing eventTime",
        ),
    ],
)
def test_parse_rejects_unsupported_or_incomplete_events(
    parser: EventParser, payload: dict[str, object], message_fragment: str
) -> None:
    with pytest.raises(ValueError, match=message_fragment):
        parser.parse(payload)


def test_parse_bytes_payload_and_private_helpers_cover_error_branches(
    parser: EventParser, blob_deleted_payload: dict[str, object]
) -> None:
    payload = dict(blob_deleted_payload)
    payload["subject"] = ""
    event = parser.parse(json.dumps(payload).encode("utf-8"))

    assert event.blob_name == "books/sample.pdf"

    with pytest.raises(ValueError, match="Unable to determine blob name"):
        parser._extract_blob_name("", "https://example.com")

    assert parser._parse_optional_int(None) is None

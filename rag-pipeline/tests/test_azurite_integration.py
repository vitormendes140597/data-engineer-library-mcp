"""Integration tests for Blob and Queue behavior against Azurite."""

from __future__ import annotations

import pytest
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient

from src.extraction.downloader import download_pdf


@pytest.mark.asyncio
async def test_upload_and_download_blob_round_trip(
    azurite_resources: object,
    blob_client: object,
    sample_pdf_bytes: bytes,
) -> None:
    uploaded = await blob_client.upload_bytes(
        "raw-pdfs",
        "round-trip/sample.pdf",
        sample_pdf_bytes,
        content_type="application/pdf",
    )

    downloaded = await download_pdf(uploaded.blob_url, azurite_resources)

    assert downloaded == sample_pdf_bytes


@pytest.mark.asyncio
async def test_queue_send_receive_delete_round_trip(queue_client: object) -> None:
    await queue_client.send_message('{"eventType":"Microsoft.Storage.BlobCreated"}')

    received = await queue_client.receive_messages()
    assert len(received) == 1
    assert received[0].content == '{"eventType":"Microsoft.Storage.BlobCreated"}'

    await queue_client.delete_message(received[0].id, received[0].pop_receipt)

    assert await queue_client.receive_messages() == []


@pytest.mark.asyncio
async def test_delete_blob_removes_artifact(
    azurite_resources: object,
    blob_client: object,
    sample_pdf_bytes: bytes,
) -> None:
    uploaded = await blob_client.upload_bytes(
        "raw-pdfs",
        "delete-me/sample.pdf",
        sample_pdf_bytes,
        content_type="application/pdf",
    )
    service = BlobServiceClient.from_connection_string(
        azurite_resources.storage.connection_string
    )

    try:
        await blob_client.delete_blob_by_url(uploaded.blob_url)
        blob = service.get_blob_client("raw-pdfs", "delete-me/sample.pdf")
        with pytest.raises(ResourceNotFoundError):
            await blob.get_blob_properties()
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_image_extraction_upload_and_retrieval(
    azurite_resources: object, blob_client: object
) -> None:
    image_bytes = b"\x89PNG\r\n\x1a\nimage-bytes"
    uploaded = await blob_client.upload_bytes(
        azurite_resources.storage.extracted_images_container,
        "images/doc-1/page-1.png",
        image_bytes,
        content_type="image/png",
    )
    service = BlobServiceClient.from_connection_string(
        azurite_resources.storage.connection_string
    )

    try:
        stream = await service.get_blob_client(
            azurite_resources.storage.extracted_images_container,
            "images/doc-1/page-1.png",
        ).download_blob()
        assert uploaded.blob_url.endswith("/extracted-images/images/doc-1/page-1.png")
        assert await stream.readall() == image_bytes
    finally:
        await service.close()

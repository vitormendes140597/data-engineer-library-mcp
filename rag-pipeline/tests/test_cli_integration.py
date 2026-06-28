"""Integration tests for local CLI helpers."""

from __future__ import annotations

import json

import pytest
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.queue.aio import QueueServiceClient
from click.testing import CliRunner

from src.cli import cli
from src.extraction.downloader import download_pdf


@pytest.fixture
def cli_env(azurite_resources: object) -> dict[str, str]:
    return {
        "STORAGE_MODE": "azurite",
        "AZURE_STORAGE_BLOB_CONN_STR": azurite_resources.storage.connection_string,
        "AZURE_STORAGE_QUEUE_CONN_STR": azurite_resources.queue.connection_string,
        "RAW_PDFS_CONTAINER": azurite_resources.storage.raw_pdfs_container,
        "EXTRACTED_IMAGES_CONTAINER": azurite_resources.storage.extracted_images_container,
        "QUEUE_NAME": azurite_resources.queue.queue_name,
        "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost/test",
        "EMBEDDING_PROVIDER": "fake",
        "FAKE_EMBEDDING_DIMENSION": "8",
    }


@pytest.mark.asyncio
async def test_cli_bootstrap_creates_containers_and_queue(
    azurite_resources: object, cli_env: dict[str, str]
) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["bootstrap"], env=cli_env)

    assert result.exit_code == 0
    assert "Bootstrap complete" in result.output

    blob_service = BlobServiceClient.from_connection_string(
        azurite_resources.storage.connection_string
    )
    queue_service = QueueServiceClient.from_connection_string(
        azurite_resources.queue.connection_string
    )
    try:
        assert await blob_service.get_container_client("raw-pdfs").exists() is True
        assert (
            await blob_service.get_container_client("extracted-images").exists() is True
        )
        queue_properties = await queue_service.get_queue_client(
            "pdf-processing-jobs"
        ).get_queue_properties()
        assert queue_properties is not None
    finally:
        await blob_service.close()
        await queue_service.close()


@pytest.mark.asyncio
async def test_cli_upload_pdf_creates_blob_and_enqueues_blobcreated(
    azurite_resources: object,
    cli_env: dict[str, str],
    sample_pdf_path: object,
) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["upload-pdf", str(sample_pdf_path)], env=cli_env)

    assert result.exit_code == 0
    assert "Enqueued BlobCreated event" in result.output

    queue_service = QueueServiceClient.from_connection_string(
        azurite_resources.queue.connection_string
    )
    queue = queue_service.get_queue_client(azurite_resources.queue.queue_name)
    try:
        messages = [
            message async for message in queue.receive_messages(messages_per_page=1)
        ]
        assert len(messages) == 1
        payload = json.loads(messages[0].content)
        assert payload["eventType"] == "Microsoft.Storage.BlobCreated"
        assert payload["data"]["contentLength"] == sample_pdf_path.stat().st_size
        assert payload["data"]["url"].endswith(f"/raw-pdfs/{sample_pdf_path.name}")
        assert payload["subject"].endswith(f"/raw-pdfs/blobs/{sample_pdf_path.name}")
        assert (
            await download_pdf(payload["data"]["url"], azurite_resources)
            == sample_pdf_path.read_bytes()
        )
    finally:
        await queue.clear_messages()
        await queue.close()
        await queue_service.close()


@pytest.mark.asyncio
async def test_cli_delete_blob_enqueues_blobdeleted(
    azurite_resources: object,
    blob_client: object,
    cli_env: dict[str, str],
    sample_pdf_bytes: bytes,
) -> None:
    uploaded = await blob_client.upload_bytes(
        azurite_resources.storage.raw_pdfs_container,
        "delete-cli/sample.pdf",
        sample_pdf_bytes,
        content_type="application/pdf",
    )
    runner = CliRunner()

    result = runner.invoke(cli, ["delete-blob", uploaded.blob_url], env=cli_env)

    assert result.exit_code == 0
    assert "Enqueued BlobDeleted event" in result.output

    queue_service = QueueServiceClient.from_connection_string(
        azurite_resources.queue.connection_string
    )
    queue = queue_service.get_queue_client(azurite_resources.queue.queue_name)
    try:
        messages = [
            message async for message in queue.receive_messages(messages_per_page=1)
        ]
        payload = json.loads(messages[0].content)
        assert payload["eventType"] == "Microsoft.Storage.BlobDeleted"
        assert payload["data"]["url"] == uploaded.blob_url
        assert payload["subject"].endswith("/raw-pdfs/blobs/delete-cli/sample.pdf")
    finally:
        await queue.clear_messages()
        await queue.close()
        await queue_service.close()

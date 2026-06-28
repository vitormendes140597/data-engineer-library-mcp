"""RAG pipeline local CLI helper for development."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    import runpy

    src_dir = Path(__file__).resolve().parent
    package_root = src_dir.parent
    sys.path = [
        str(package_root),
        *[path for path in sys.path if Path(path or ".").resolve() != src_dir],
    ]
    runpy.run_module("src.cli", run_name="__main__")
    raise SystemExit(0)

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar
from uuid import uuid4

import click
from azure.core.exceptions import ResourceExistsError

from src.blob.client import BlobClient
from src.config import RAGConfig
from src.queue.client import QueueClient

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("azure").setLevel(logging.WARNING)


def _run_async(async_fn: Callable[..., Awaitable[T]], *args: object) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_fn(*args))

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(async_fn(*args))).result()


@click.group()
def cli() -> None:
    """RAG pipeline local development helper."""


@cli.command()
@click.argument(
    "pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--container", default="raw-pdfs", help="Blob container name (default: raw-pdfs)"
)
def upload_pdf(pdf_path: Path, container: str) -> None:
    """Upload a PDF to Azurite and enqueue a BlobCreated event."""
    _run_async(_upload_pdf_async, pdf_path, container)


@cli.command()
@click.argument("blob_url")
def delete_blob(blob_url: str) -> None:
    """Enqueue a BlobDeleted event for an Azurite blob URL."""
    _run_async(_delete_blob_async, blob_url)


@cli.command()
def bootstrap() -> None:
    """Bootstrap local Azurite containers and queue."""
    _run_async(_bootstrap_async)


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_subject(container: str, blob_name: str) -> str:
    return f"/blobServices/default/containers/{container}/blobs/{blob_name}"


def _build_blob_created_event(
    *,
    container: str,
    blob_name: str,
    blob_url: str,
    content_length: int,
    etag: str | None,
) -> dict[str, object]:
    return {
        "eventType": "Microsoft.Storage.BlobCreated",
        "subject": _build_subject(container, blob_name),
        "eventTime": _iso_utc_now(),
        "id": str(uuid4()),
        "data": {
            "api": "PutBlob",
            "clientRequestId": str(uuid4()),
            "requestId": str(uuid4()),
            "eTag": etag,
            "contentType": "application/pdf",
            "contentLength": content_length,
            "blobType": "BlockBlob",
            "url": blob_url,
        },
    }


def _build_blob_deleted_event(
    *,
    container: str,
    blob_name: str,
    blob_url: str,
) -> dict[str, object]:
    return {
        "eventType": "Microsoft.Storage.BlobDeleted",
        "subject": _build_subject(container, blob_name),
        "eventTime": _iso_utc_now(),
        "id": str(uuid4()),
        "data": {
            "api": "DeleteBlob",
            "clientRequestId": str(uuid4()),
            "requestId": str(uuid4()),
            "blobType": "BlockBlob",
            "url": blob_url,
        },
    }


async def _upload_pdf_async(pdf_path: Path, container: str) -> None:
    """Upload a PDF to blob storage and enqueue a BlobCreated event."""
    _configure_logging()

    queue_client: QueueClient | None = None
    blob_client: BlobClient | None = None

    try:
        config = RAGConfig.from_env()
        _ensure_azurite_mode(config)

        blob_client = BlobClient(config.storage)
        queue_client = QueueClient(config.queue)

        uploaded_blob = await blob_client.upload_file(
            container, pdf_path.name, pdf_path
        )
        event = _build_blob_created_event(
            container=container,
            blob_name=pdf_path.name,
            blob_url=uploaded_blob.blob_url,
            content_length=uploaded_blob.content_length,
            etag=uploaded_blob.etag,
        )
        await queue_client.send_message(json.dumps(event))

        click.echo(f"✓ Uploaded {pdf_path.name} ({uploaded_blob.content_length} bytes)")
        click.echo("✓ Enqueued BlobCreated event")
    except Exception as exc:
        logger.exception("Error uploading PDF: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    finally:
        if queue_client is not None:
            await queue_client.close()
        if blob_client is not None:
            await blob_client.close()


async def _delete_blob_async(blob_url: str) -> None:
    """Enqueue a BlobDeleted event for a blob URL."""
    _configure_logging()

    queue_client: QueueClient | None = None
    blob_client: BlobClient | None = None

    try:
        config = RAGConfig.from_env()
        _ensure_azurite_mode(config)

        blob_client = BlobClient(config.storage)
        container, blob_name = blob_client.parse_blob_url(blob_url)
        queue_client = QueueClient(config.queue)

        event = _build_blob_deleted_event(
            container=container,
            blob_name=blob_name,
            blob_url=blob_url,
        )
        await queue_client.send_message(json.dumps(event))
        click.echo(f"✓ Enqueued BlobDeleted event for {blob_url}")
    except Exception as exc:
        logger.exception("Error enqueueing delete event: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    finally:
        if queue_client is not None:
            await queue_client.close()
        if blob_client is not None:
            await blob_client.close()


async def _bootstrap_async() -> None:
    """Async bootstrap of local services."""
    _configure_logging()

    try:
        config = RAGConfig.from_env()
        _ensure_azurite_mode(config)

        from azure.storage.blob.aio import BlobServiceClient
        from azure.storage.queue.aio import QueueServiceClient

        blob_service = BlobServiceClient.from_connection_string(
            config.storage.connection_string
        )
        try:
            for container_name in [
                config.storage.raw_pdfs_container,
                config.storage.extracted_images_container,
            ]:
                try:
                    await blob_service.get_container_client(
                        container_name
                    ).create_container()
                    click.echo(f"✓ Created blob container: {container_name}")
                except ResourceExistsError:
                    click.echo(f"✓ Blob container already exists: {container_name}")
        finally:
            await blob_service.close()

        queue_service = QueueServiceClient.from_connection_string(
            config.queue.connection_string
        )
        try:
            queue = queue_service.get_queue_client(config.queue.queue_name)
            try:
                await queue.create_queue()
                click.echo(f"✓ Created storage queue: {config.queue.queue_name}")
            except ResourceExistsError:
                click.echo(f"✓ Storage queue already exists: {config.queue.queue_name}")
            finally:
                await queue.close()
        finally:
            await queue_service.close()

        click.echo("\n✓ Bootstrap complete!")
    except Exception as exc:
        logger.exception("Error bootstrapping: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _ensure_azurite_mode(config: RAGConfig) -> None:
    if config.storage.storage_mode != "azurite":
        raise click.ClickException(
            "this helper only works with STORAGE_MODE=azurite, "
            f"got {config.storage.storage_mode}"
        )


if __name__ == "__main__":
    cli()

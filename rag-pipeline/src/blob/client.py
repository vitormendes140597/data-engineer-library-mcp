"""Async Azure Blob Storage client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobClient as AzureBlobClient
from azure.storage.blob.aio import BlobServiceClient

from src.config import StorageConfig


@dataclass(slots=True)
class UploadedBlob:
    """Uploaded blob metadata used for Event Grid payloads."""

    blob_url: str
    etag: str | None
    content_length: int


class BlobClient:
    """Async Blob Storage operations for source PDFs and extracted images."""

    def __init__(self, config: StorageConfig):
        self._config = config
        self._client = BlobServiceClient.from_connection_string(
            config.connection_string
        )

    def parse_blob_url(self, blob_url: str) -> tuple[str, str]:
        """Parse a blob URL into container name and blob path."""
        parsed = urlparse(blob_url)
        path_parts = [part for part in parsed.path.split("/") if part]

        if self._config.storage_mode == "azurite":
            if len(path_parts) < 3:
                raise ValueError(f"Invalid Azurite blob URL: {blob_url}")
            container = path_parts[1]
            blob_path = "/".join(path_parts[2:])
            return container, unquote(blob_path)

        if len(path_parts) < 2:
            raise ValueError(f"Invalid blob URL: {blob_url}")

        container = path_parts[0]
        blob_path = "/".join(path_parts[1:])
        return container, unquote(blob_path)

    def get_blob_client(self, container: str, blob_name: str) -> AzureBlobClient:
        """Return an SDK blob client for advanced upload and download operations."""
        return self._client.get_blob_client(container=container, blob=blob_name)

    async def upload_file(
        self,
        container: str,
        blob_name: str,
        file_path: str | Path,
        *,
        overwrite: bool = True,
        content_type: str = "application/pdf",
    ) -> UploadedBlob:
        """Upload a local file and return the blob URL, ETag, and size."""
        path = Path(file_path)

        with path.open("rb") as file_handle:
            return await self.upload_bytes(
                container,
                blob_name,
                file_handle,
                overwrite=overwrite,
                content_type=content_type,
            )

    async def upload_bytes(
        self,
        container: str,
        blob_name: str,
        data: bytes | object,
        *,
        overwrite: bool = True,
        content_type: str = "application/octet-stream",
    ) -> UploadedBlob:
        """Upload bytes or a byte stream and return blob metadata."""
        blob_client = self.get_blob_client(container=container, blob_name=blob_name)
        await blob_client.upload_blob(
            data,
            overwrite=overwrite,
            content_settings=ContentSettings(content_type=content_type),
        )
        properties = await blob_client.get_blob_properties()
        return UploadedBlob(
            blob_url=blob_client.url,
            etag=properties.etag,
            content_length=properties.size,
        )

    async def delete_blob(self, container: str, blob_name: str) -> None:
        """Delete a blob if it exists."""
        blob_client = self._client.get_blob_client(container=container, blob=blob_name)
        try:
            await blob_client.delete_blob(delete_snapshots="include")
        except ResourceNotFoundError:
            return

    async def delete_blob_by_url(self, blob_url: str) -> None:
        """Delete a blob referenced by its full URL."""
        container, blob_name = self.parse_blob_url(blob_url)
        await self.delete_blob(container, blob_name)

    async def delete_extracted_image_blob(self, blob_path: str) -> None:
        """Delete one extracted image blob if it exists."""
        await self.delete_blob(self._config.extracted_images_container, blob_path)

    async def delete_extracted_image_blobs(self, blob_paths: Sequence[str]) -> None:
        """Delete extracted image blobs stored for a document."""
        for blob_path in blob_paths:
            await self.delete_extracted_image_blob(blob_path)

    async def close(self) -> None:
        """Close the underlying async SDK client."""
        await self._client.close()

    async def __aenter__(self) -> "BlobClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

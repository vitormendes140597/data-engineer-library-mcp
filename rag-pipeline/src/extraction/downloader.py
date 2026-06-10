"""Blob download helpers for PDF extraction."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

from azure.identity.aio import (ClientSecretCredential, DefaultAzureCredential,
                                ManagedIdentityCredential)
from azure.storage.blob.aio import BlobClient, BlobServiceClient

from src.config import RAGConfig


async def download_pdf(blob_url: str, config: RAGConfig) -> bytes:
    """Download a PDF blob using Azurite or Azure credentials from config."""
    credential = None
    blob_service_client = None
    blob_client = None

    try:
        if _is_azurite_blob_url(blob_url, config):
            container, blob_name = _parse_blob_url(
                blob_url, config.storage.storage_mode
            )
            blob_service_client = BlobServiceClient.from_connection_string(
                config.storage.connection_string
            )
            blob_client = blob_service_client.get_blob_client(
                container=container,
                blob=blob_name,
            )
        else:
            credential = _build_credential(config)
            blob_client = BlobClient.from_blob_url(blob_url, credential=credential)

        stream = await blob_client.download_blob()
        return await stream.readall()
    finally:
        if blob_client is not None:
            await blob_client.close()
        if blob_service_client is not None:
            await blob_service_client.close()
        if credential is not None:
            await credential.close()


def _is_azurite_blob_url(blob_url: str, config: RAGConfig) -> bool:
    parsed = urlparse(blob_url)
    host = (parsed.hostname or "").lower()
    return (
        config.storage.storage_mode == "azurite"
        or host in {"127.0.0.1", "localhost"}
        or "devstoreaccount1" in parsed.path
    )


def _parse_blob_url(blob_url: str, storage_mode: str) -> tuple[str, str]:
    parsed = urlparse(blob_url)
    path_parts = [part for part in parsed.path.split("/") if part]

    if storage_mode == "azurite" or "devstoreaccount1" in parsed.path:
        if len(path_parts) < 3:
            raise ValueError(f"Invalid Azurite blob URL: {blob_url}")
        return path_parts[1], unquote("/".join(path_parts[2:]))

    if len(path_parts) < 2:
        raise ValueError(f"Invalid Azure blob URL: {blob_url}")

    return path_parts[0], unquote("/".join(path_parts[1:]))


def _build_credential(config: RAGConfig) -> Any:
    identity = config.azure_identity

    if identity.tenant_id and identity.client_id and identity.client_secret:
        return ClientSecretCredential(
            tenant_id=identity.tenant_id,
            client_id=identity.client_id,
            client_secret=identity.client_secret,
        )

    if identity.use_managed_identity:
        return ManagedIdentityCredential(client_id=identity.client_id or None)

    return DefaultAzureCredential(
        managed_identity_client_id=identity.client_id or None,
    )

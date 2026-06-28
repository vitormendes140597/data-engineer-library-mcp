"""Extract images from PDFs and upload them to blob storage."""

from __future__ import annotations

from typing import Any

import fitz
from azure.storage.blob import ContentSettings

from src.config import RAGConfig

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "webp": "image/webp",
}


async def extract_and_upload_images(
    pdf_bytes: bytes,
    document_id: str,
    blob_client: Any,
    config: RAGConfig,
) -> list[dict[str, Any]]:
    """Extract PDF images, upload them to blob storage, and return their metadata."""
    service_client = _resolve_blob_service_client(blob_client)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        extracted_images: list[dict[str, Any]] = []

        for page_number, page in enumerate(document, start=1):
            for image_index, image_info in enumerate(
                page.get_images(full=True), start=1
            ):
                xref = image_info[0]
                if xref <= 0:
                    continue

                image_data = document.extract_image(xref)
                image_bytes = image_data.get("image")
                if not image_bytes:
                    continue

                image_format = str(image_data.get("ext", "png")).lower()
                blob_path = (
                    f"documents/{document_id}/page_{page_number}/"
                    f"image_{image_index}.{image_format}"
                )
                client = service_client.get_blob_client(
                    config.storage.extracted_images_container,
                    blob_path,
                )
                await client.upload_blob(
                    image_bytes,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type=_CONTENT_TYPES.get(
                            image_format, "application/octet-stream"
                        )
                    ),
                )

                rects = page.get_image_rects(xref)
                bbox = None
                if rects:
                    rect = rects[0]
                    bbox = [rect.x0, rect.y0, rect.x1, rect.y1]

                extracted_images.append(
                    {
                        "source_page": page_number,
                        "blob_path": blob_path,
                        "blob_url": client.url,
                        "format": image_format.upper(),
                        "width": image_data.get("width"),
                        "height": image_data.get("height"),
                        "bbox": bbox,
                        "metadata": {},
                    }
                )
                await client.close()

        return extracted_images
    finally:
        document.close()


def _resolve_blob_service_client(blob_client: Any) -> Any:
    if hasattr(blob_client, "get_blob_client"):
        return blob_client

    underlying_client = getattr(blob_client, "_client", None)
    if underlying_client is not None and hasattr(underlying_client, "get_blob_client"):
        return underlying_client

    raise TypeError(
        "blob_client must expose get_blob_client() or wrap BlobServiceClient"
    )

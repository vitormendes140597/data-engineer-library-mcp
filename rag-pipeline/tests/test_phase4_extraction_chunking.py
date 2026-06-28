import fitz
import pytest

from src.chunking.chunker import chunk_text
from src.chunking.image_linking import link_chunks_to_images, store_chunk_image_links
from src.config import ChunkingConfig
from src.extraction.image_extractor import extract_and_upload_images
from src.extraction.pdf_parser import extract_markdown


class _FakeUploadedImageBlobClient:
    def __init__(self, container: str, blob_name: str):
        self.container = container
        self.blob_name = blob_name
        self.url = f"https://example.test/{container}/{blob_name}"
        self.uploads: list[dict[str, object]] = []
        self.closed = False

    async def upload_blob(self, data: bytes, **kwargs: object) -> None:
        self.uploads.append({"data": data, **kwargs})

    async def close(self) -> None:
        self.closed = True


class _FakePipelineBlobClient:
    def __init__(self):
        self.created_clients: list[_FakeUploadedImageBlobClient] = []

    def get_blob_client(
        self, container: str, blob_name: str
    ) -> _FakeUploadedImageBlobClient:
        client = _FakeUploadedImageBlobClient(container, blob_name)
        self.created_clients.append(client)
        return client


@pytest.mark.asyncio
async def test_extract_markdown_preserves_page_content_and_headings():
    document = fitz.open()
    page_one = document.new_page()
    page_one.insert_text((72, 72), "Document Title", fontsize=24)
    page_one.insert_text((72, 110), "Section Heading", fontsize=18)
    page_one.insert_text((72, 150), "Body content on the first page.", fontsize=12)

    page_two = document.new_page()
    page_two.insert_text((72, 72), "Continuation on the second page.", fontsize=12)

    pdf_bytes = document.tobytes()
    document.close()

    result = await extract_markdown(pdf_bytes)

    assert result["page_contents"][1].startswith("# Document Title")
    assert "## Section Heading" in result["page_contents"][1]
    assert result["pages"][1]["text"] == "Continuation on the second page."
    assert "Continuation on the second page." in result["text"]


@pytest.mark.asyncio
async def test_extract_and_upload_images_uses_pipeline_blob_client_signature(
    rag_config,
):
    document = fitz.open()
    page = document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), 0)
    pixmap.clear_with(0x336699)
    page.insert_image(fitz.Rect(72, 72, 120, 120), pixmap=pixmap)
    pdf_bytes = document.tobytes()
    document.close()

    blob_client = _FakePipelineBlobClient()

    images = await extract_and_upload_images(
        pdf_bytes,
        document_id="document-1",
        blob_client=blob_client,
        config=rag_config,
    )

    assert len(images) == 1
    assert images[0]["blob_path"].startswith("documents/document-1/page_1/image_1.")
    assert blob_client.created_clients[0].container == "extracted-images"
    assert blob_client.created_clients[0].blob_name == images[0]["blob_path"]
    assert blob_client.created_clients[0].uploads
    assert blob_client.created_clients[0].closed is True


@pytest.mark.asyncio
async def test_chunk_text_tracks_page_ranges_and_heading_metadata():
    markdown_pages = {
        1: "# Intro\n\n" + ("alpha " * 20),
        2: "## Details\n\n" + ("beta " * 20),
    }
    config = ChunkingConfig(chunk_size=400, chunk_overlap=25)

    chunks = await chunk_text(markdown_pages, config)

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 2
    assert chunks[0]["heading"] == "Intro"
    assert chunks[0]["metadata"]["page_range"] == [1, 2]


@pytest.mark.asyncio
async def test_link_chunks_to_images_uses_inclusive_page_ranges():
    chunks = [
        {"chunk_index": 0, "page_start": 1, "page_end": 2},
        {"chunk_index": 1, "page_start": 3, "page_end": 3},
    ]
    images = [
        {"source_page": 2},
        {"source_page": 3},
        {"source_page": 4},
    ]

    links = await link_chunks_to_images(chunks, images)
    stored_links = await store_chunk_image_links(
        ["chunk-0", "chunk-1"], ["image-0", "image-1", "image-2"], links
    )

    assert links == [(0, 0), (1, 1)]
    assert stored_links == [("chunk-0", "image-0"), ("chunk-1", "image-1")]

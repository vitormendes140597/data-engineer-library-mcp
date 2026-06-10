from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from uuid import uuid4

import fitz
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from azure.core.exceptions import ResourceExistsError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from testcontainers.core.container import DockerContainer

from src.blob.client import BlobClient
from src.config import (
    AzureIdentityConfig,
    ChunkingConfig,
    DatabaseConfig,
    EmbeddingConfig,
    QueueConfig,
    RAGConfig,
    RetryConfig,
    StorageConfig,
)
from src.persistence.repository import Repository
from src.queue.client import QueueClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_RUNTIME_ROOT = PROJECT_ROOT / "tests" / ".runtime"
AZURITE_ACCOUNT_NAME = "devstoreaccount1"
AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw=="
)


def _build_test_config(
    *,
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost/test",
    blob_connection_string: str = "UseDevelopmentStorage=true",
    queue_connection_string: str = "UseDevelopmentStorage=true",
) -> RAGConfig:
    return RAGConfig(
        queue=QueueConfig(
            AZURE_STORAGE_QUEUE_CONN_STR=queue_connection_string,
            QUEUE_NAME="pdf-processing-jobs",
            QUEUE_VISIBILITY_TIMEOUT_SECONDS=30,
            QUEUE_MAX_RECEIVE_MESSAGES=1,
        ),
        storage=StorageConfig(
            AZURE_STORAGE_BLOB_CONN_STR=blob_connection_string,
            RAW_PDFS_CONTAINER="raw-pdfs",
            EXTRACTED_IMAGES_CONTAINER="extracted-images",
            STORAGE_MODE="azurite",
        ),
        database=DatabaseConfig(DATABASE_URL=database_url),
        embedding=EmbeddingConfig(
            provider="fake",
            fake_dimension=8,
            batch_size=2,
            max_tokens_per_batch=8,
        ),
        chunking=ChunkingConfig(chunk_size=400, chunk_overlap=50),
        retry=RetryConfig(max_attempts=3, initial_delay_seconds=5, max_delay_seconds=20),
        azure_identity=AzureIdentityConfig(),
        OBSERVABILITY_ENABLED=False,
    )


@pytest.fixture(scope="session")
def runtime_root() -> Path:
    TEST_RUNTIME_ROOT.mkdir(exist_ok=True)
    yield TEST_RUNTIME_ROOT
    shutil.rmtree(TEST_RUNTIME_ROOT, ignore_errors=True)


@pytest.fixture
def artifact_dir(runtime_root: Path) -> Path:
    path = runtime_root / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Sample PDF", fontsize=24)
    page.insert_text((72, 108), "This document is used by the integration tests.")
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


@pytest.fixture
def sample_pdf_path(artifact_dir: Path, sample_pdf_bytes: bytes) -> Path:
    path = artifact_dir / "sample.pdf"
    path.write_bytes(sample_pdf_bytes)
    return path


@pytest.fixture
def blob_created_payload() -> dict[str, object]:
    return {
        "id": "event-created-1",
        "eventType": "Microsoft.Storage.BlobCreated",
        "subject": "/blobServices/default/containers/raw-pdfs/blobs/books/sample.pdf",
        "eventTime": "2026-01-01T00:00:00Z",
        "data": {
            "url": "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/books/sample.pdf",
            "contentLength": 123,
            "eTag": '"etag-created-1"',
            "blobType": "BlockBlob",
        },
    }


@pytest.fixture
def blob_deleted_payload() -> dict[str, object]:
    return {
        "id": "event-deleted-1",
        "eventType": "Microsoft.Storage.BlobDeleted",
        "subject": "/blobServices/default/containers/raw-pdfs/blobs/books/sample.pdf",
        "eventTime": "2026-01-01T00:00:00Z",
        "data": {
            "url": "http://127.0.0.1:10000/devstoreaccount1/raw-pdfs/books/sample.pdf",
            "blobType": "BlockBlob",
        },
    }


@pytest.fixture
def rag_config() -> RAGConfig:
    return _build_test_config()


@pytest.fixture(scope="session")
def postgres_server() -> dict[str, str]:
    data_dir = TEST_RUNTIME_ROOT / f"postgres-{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=True)

    container = (
        DockerContainer("pgvector/pgvector:pg16")
        .with_env("POSTGRES_DB", "postgres")
        .with_env("POSTGRES_USER", "postgres")
        .with_env("POSTGRES_PASSWORD", "postgres")
        .with_volume_mapping(str(data_dir), "/var/lib/postgresql/data", mode="rw")
        .with_exposed_ports(5432)
    )
    try:
        with container as postgres:
            host = postgres.get_container_host_ip()
            port = postgres.get_exposed_port(5432)
            admin_url = f"postgresql+psycopg://postgres:postgres@{host}:{port}/postgres"

            for _ in range(60):
                try:
                    engine = create_engine(admin_url)
                    with engine.connect() as connection:
                        connection.execute(text("SELECT 1"))
                    engine.dispose()
                    break
                except OperationalError:
                    time.sleep(1)
            else:  # pragma: no cover - container startup failure
                raise RuntimeError("PostgreSQL test container did not become ready")

            yield {"admin_url": admin_url}
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def postgres_database_url(postgres_server: dict[str, str]) -> str:
    database_name = f"rag_test_{uuid4().hex}"
    admin_engine = create_engine(
        postgres_server["admin_url"], isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    admin_engine.dispose()

    database_url = postgres_server["admin_url"].rsplit("/", 1)[0] + f"/{database_name}"

    try:
        yield database_url
    finally:
        admin_engine = create_engine(
            postgres_server["admin_url"], isolation_level="AUTOCOMMIT"
        )
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


@pytest.fixture
def migrated_database_url(postgres_database_url: str) -> str:
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_database_url

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    alembic_config.attributes["configure_logger"] = False
    command.upgrade(alembic_config, "head")

    try:
        yield postgres_database_url
    finally:
        command.downgrade(alembic_config, "base")
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@pytest_asyncio.fixture
async def repository(migrated_database_url: str) -> Repository:
    repo = Repository(DatabaseConfig(DATABASE_URL=migrated_database_url))
    try:
        yield repo
    finally:
        await repo.dispose()


@pytest.fixture(scope="session")
def azurite_service() -> dict[str, str]:
    container = (
        DockerContainer("mcr.microsoft.com/azure-storage/azurite:latest")
        .with_command(
            "azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --skipApiVersionCheck"
        )
        .with_exposed_ports(10000, 10001)
    )
    with container as azurite:
        host = azurite.get_container_host_ip()
        blob_port = azurite.get_exposed_port(10000)
        queue_port = azurite.get_exposed_port(10001)
        connection_string = (
            "DefaultEndpointsProtocol=http;"
            f"AccountName={AZURITE_ACCOUNT_NAME};"
            f"AccountKey={AZURITE_ACCOUNT_KEY};"
            f"BlobEndpoint=http://{host}:{blob_port}/{AZURITE_ACCOUNT_NAME};"
            f"QueueEndpoint=http://{host}:{queue_port}/{AZURITE_ACCOUNT_NAME};"
        )

        from azure.storage.blob import BlobServiceClient
        from azure.storage.queue import QueueServiceClient

        for _ in range(60):
            try:
                blob_service = BlobServiceClient.from_connection_string(
                    connection_string
                )
                queue_service = QueueServiceClient.from_connection_string(
                    connection_string
                )
                list(blob_service.list_containers())
                list(queue_service.list_queues())
                break
            except Exception:
                time.sleep(1)
        else:  # pragma: no cover - container startup failure
            raise RuntimeError("Azurite test container did not become ready")

        yield {
            "connection_string": connection_string,
            "blob_endpoint": f"http://{host}:{blob_port}/{AZURITE_ACCOUNT_NAME}",
            "queue_endpoint": f"http://{host}:{queue_port}/{AZURITE_ACCOUNT_NAME}",
        }


@pytest.fixture
def azurite_config(azurite_service: dict[str, str]) -> RAGConfig:
    return _build_test_config(
        blob_connection_string=azurite_service["connection_string"],
        queue_connection_string=azurite_service["connection_string"],
    )


async def _clear_blob_container(container_client: object) -> None:
    async for blob in container_client.list_blobs():
        await container_client.delete_blob(blob.name, delete_snapshots="include")


@pytest_asyncio.fixture
async def azurite_resources(azurite_config: RAGConfig) -> RAGConfig:
    from azure.storage.blob.aio import BlobServiceClient
    from azure.storage.queue.aio import QueueServiceClient

    blob_service = BlobServiceClient.from_connection_string(
        azurite_config.storage.connection_string
    )
    queue_service = QueueServiceClient.from_connection_string(
        azurite_config.queue.connection_string
    )
    raw_container = blob_service.get_container_client(
        azurite_config.storage.raw_pdfs_container
    )
    extracted_container = blob_service.get_container_client(
        azurite_config.storage.extracted_images_container
    )
    queue = queue_service.get_queue_client(azurite_config.queue.queue_name)

    try:
        for container_client in [raw_container, extracted_container]:
            try:
                await container_client.create_container()
            except ResourceExistsError:
                pass
            await _clear_blob_container(container_client)

        try:
            await queue.create_queue()
        except ResourceExistsError:
            pass
        await queue.clear_messages()

        yield azurite_config
    finally:
        await queue.clear_messages()
        await queue.close()
        await _clear_blob_container(raw_container)
        await _clear_blob_container(extracted_container)
        await raw_container.close()
        await extracted_container.close()
        await blob_service.close()
        await queue_service.close()


@pytest_asyncio.fixture
async def blob_client(azurite_resources: RAGConfig) -> BlobClient:
    client = BlobClient(azurite_resources.storage)
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture
async def queue_client(azurite_resources: RAGConfig) -> QueueClient:
    client = QueueClient(azurite_resources.queue)
    try:
        yield client
    finally:
        await client.close()

"""Configuration loading for the RAG pipeline."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


def _load_local_env() -> None:
    """Load local dotenv values without overriding real environment variables."""
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file, override=False)


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable."""
    return os.getenv(name, str(default)).lower() == "true"


class QueueConfig(BaseModel):
    """Storage Queue configuration."""

    model_config = ConfigDict(populate_by_name=True)

    connection_string: str = Field(..., alias="AZURE_STORAGE_QUEUE_CONN_STR")
    queue_name: str = Field(default="pdf-processing-jobs", alias="QUEUE_NAME")
    visibility_timeout: int = Field(
        default=3600, alias="QUEUE_VISIBILITY_TIMEOUT_SECONDS"
    )
    max_receive_messages: int = Field(default=1, alias="QUEUE_MAX_RECEIVE_MESSAGES")


class StorageConfig(BaseModel):
    """Blob Storage configuration."""

    model_config = ConfigDict(populate_by_name=True)

    connection_string: str = Field(..., alias="AZURE_STORAGE_BLOB_CONN_STR")
    raw_pdfs_container: str = Field(default="raw-pdfs", alias="RAW_PDFS_CONTAINER")
    extracted_images_container: str = Field(
        default="extracted-images", alias="EXTRACTED_IMAGES_CONTAINER"
    )
    storage_mode: Literal["azure", "azurite"] = Field(
        default="azurite", alias="STORAGE_MODE"
    )


class DatabaseConfig(BaseModel):
    """PostgreSQL configuration."""

    model_config = ConfigDict(populate_by_name=True)

    connection_string: str = Field(..., alias="DATABASE_URL")
    pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    echo_sql: bool = Field(default=False, alias="DB_ECHO_SQL")


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    model_config = ConfigDict(populate_by_name=True)

    provider: Literal["fake", "azure_ai_foundry"] = Field(
        default="fake", alias="EMBEDDING_PROVIDER"
    )
    fake_dimension: int = Field(default=1536, alias="FAKE_EMBEDDING_DIMENSION")
    azure_ai_foundry_project: str = Field(default="", alias="AZURE_AI_FOUNDRY_PROJECT")
    azure_ai_foundry_endpoint: str = Field(
        default="", alias="AZURE_AI_FOUNDRY_ENDPOINT"
    )
    azure_ai_foundry_deployment: str = Field(
        default="", alias="AZURE_AI_FOUNDRY_DEPLOYMENT"
    )
    batch_size: int = Field(default=25, alias="EMBEDDING_BATCH_SIZE")
    max_tokens_per_batch: int = Field(
        default=8000, alias="EMBEDDING_MAX_TOKENS_PER_BATCH"
    )


class ChunkingConfig(BaseModel):
    """Text chunking configuration."""

    model_config = ConfigDict(populate_by_name=True)

    chunk_size: int = Field(default=1024, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=128, alias="CHUNK_OVERLAP")
    separators: list[str] = Field(
        default_factory=lambda: ["\n\n", "\n", " "], alias="CHUNK_SEPARATORS"
    )


class RetryConfig(BaseModel):
    """Retry and failure handling configuration."""

    model_config = ConfigDict(populate_by_name=True)

    max_attempts: int = Field(default=3, alias="MAX_RETRY_ATTEMPTS")
    initial_delay_seconds: int = Field(default=300, alias="INITIAL_RETRY_DELAY_SECONDS")
    max_delay_seconds: int = Field(default=3600, alias="MAX_RETRY_DELAY_SECONDS")


class AzureIdentityConfig(BaseModel):
    """Azure Identity configuration for managed credentials."""

    model_config = ConfigDict(populate_by_name=True)

    use_managed_identity: bool = Field(default=True, alias="USE_MANAGED_IDENTITY")
    tenant_id: str = Field(default="", alias="AZURE_TENANT_ID")
    client_id: str = Field(default="", alias="AZURE_CLIENT_ID")
    client_secret: str = Field(default="", alias="AZURE_CLIENT_SECRET")


def _build_queue_config() -> QueueConfig:
    return QueueConfig(
        connection_string=os.getenv("AZURE_STORAGE_QUEUE_CONN_STR", ""),
        queue_name=os.getenv("QUEUE_NAME", "pdf-processing-jobs"),
        visibility_timeout=int(os.getenv("QUEUE_VISIBILITY_TIMEOUT_SECONDS", "3600")),
        max_receive_messages=int(os.getenv("QUEUE_MAX_RECEIVE_MESSAGES", "1")),
    )


def _build_storage_config() -> StorageConfig:
    return StorageConfig(
        connection_string=os.getenv("AZURE_STORAGE_BLOB_CONN_STR", ""),
        raw_pdfs_container=os.getenv("RAW_PDFS_CONTAINER", "raw-pdfs"),
        extracted_images_container=os.getenv(
            "EXTRACTED_IMAGES_CONTAINER", "extracted-images"
        ),
        storage_mode=os.getenv("STORAGE_MODE", "azurite"),
    )


def _build_database_config() -> DatabaseConfig:
    return DatabaseConfig(
        connection_string=os.getenv("DATABASE_URL", ""),
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        echo_sql=_get_bool("DB_ECHO_SQL", False),
    )


def _build_embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        provider=os.getenv("EMBEDDING_PROVIDER", "fake"),
        fake_dimension=int(os.getenv("FAKE_EMBEDDING_DIMENSION", "1536")),
        azure_ai_foundry_project=os.getenv("AZURE_AI_FOUNDRY_PROJECT", ""),
        azure_ai_foundry_endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", ""),
        azure_ai_foundry_deployment=os.getenv("AZURE_AI_FOUNDRY_DEPLOYMENT", ""),
        batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "25")),
        max_tokens_per_batch=int(os.getenv("EMBEDDING_MAX_TOKENS_PER_BATCH", "8000")),
    )


def _build_chunking_config() -> ChunkingConfig:
    return ChunkingConfig(
        chunk_size=int(os.getenv("CHUNK_SIZE", "1024")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "128")),
    )


def _build_retry_config() -> RetryConfig:
    return RetryConfig(
        max_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
        initial_delay_seconds=int(os.getenv("INITIAL_RETRY_DELAY_SECONDS", "300")),
        max_delay_seconds=int(os.getenv("MAX_RETRY_DELAY_SECONDS", "3600")),
    )


def _build_azure_identity_config() -> AzureIdentityConfig:
    return AzureIdentityConfig(
        use_managed_identity=_get_bool("USE_MANAGED_IDENTITY", True),
        tenant_id=os.getenv("AZURE_TENANT_ID", ""),
        client_id=os.getenv("AZURE_CLIENT_ID", ""),
        client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
    )


_load_local_env()
DATABASE_URL = os.getenv("DATABASE_URL", "")
EMBEDDING_CONFIG = _build_embedding_config()
VECTOR_DIMENSION = EMBEDDING_CONFIG.fake_dimension


class RAGConfig(BaseModel):
    """Complete RAG pipeline configuration."""

    model_config = ConfigDict(populate_by_name=True)

    queue: QueueConfig
    storage: StorageConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    chunking: ChunkingConfig
    retry: RetryConfig
    azure_identity: AzureIdentityConfig
    observability_enabled: bool = Field(default=True, alias="OBSERVABILITY_ENABLED")

    @classmethod
    def from_env(cls) -> "RAGConfig":
        """Load configuration from environment variables and .env file."""
        _load_local_env()
        return cls(
            queue=_build_queue_config(),
            storage=_build_storage_config(),
            database=_build_database_config(),
            embedding=_build_embedding_config(),
            chunking=_build_chunking_config(),
            retry=_build_retry_config(),
            azure_identity=_build_azure_identity_config(),
            observability_enabled=_get_bool("OBSERVABILITY_ENABLED", True),
        )

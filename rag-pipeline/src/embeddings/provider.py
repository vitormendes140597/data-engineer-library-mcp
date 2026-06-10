"""Embedding provider implementations for the RAG pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import random
from abc import ABC, abstractmethod
from collections.abc import Callable

from azure.ai.projects.aio import AIProjectClient as ProjectClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from openai import (APIConnectionError, APIStatusError, APITimeoutError,
                    AsyncOpenAI, InternalServerError, RateLimitError)

from src.config import EmbeddingConfig

logger = logging.getLogger(__name__)
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for the supplied text."""

    async def close(self) -> None:
        """Release any provider resources."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic fake embedding provider for local development and tests."""

    def __init__(self, config: EmbeddingConfig):
        self._config = config

    async def embed_text(self, text: str) -> list[float]:
        if self._config.fake_dimension <= 0:
            raise ValueError("FAKE_EMBEDDING_DIMENSION must be greater than zero")

        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
        generator = random.Random(seed)
        return [
            generator.uniform(-1.0, 1.0) for _ in range(self._config.fake_dimension)
        ]


class AzureAIFoundryEmbeddingProvider(EmbeddingProvider):
    """Azure AI Foundry embedding provider backed by Azure AI Projects."""

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        credential: AsyncTokenCredential | None = None,
        project_client_factory: Callable[..., ProjectClient] | None = None,
    ):
        self._config = config
        self._credential = credential
        self._owns_credential = credential is None
        self._project_client_factory = project_client_factory or ProjectClient
        self._project_client: ProjectClient | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._project_endpoint = self._build_project_endpoint(
            config.azure_ai_foundry_endpoint,
            config.azure_ai_foundry_project,
        )

    async def embed_text(self, text: str) -> list[float]:
        if not self._config.azure_ai_foundry_deployment:
            raise ValueError("AZURE_AI_FOUNDRY_DEPLOYMENT must be configured")

        openai_client = await self._get_openai_client()

        for attempt in range(3):
            try:
                response = await openai_client.embeddings.create(
                    input=[text],
                    model=self._config.azure_ai_foundry_deployment,
                )
                if not response.data:
                    raise ValueError("Azure AI Foundry returned no embedding data")
                return list(response.data[0].embedding)
            except (
                RateLimitError,
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
            ) as exc:
                if attempt == 2:
                    raise
                delay_seconds = 2**attempt
                logger.warning(
                    "Transient Azure AI Foundry embedding error on attempt %s/3: %s",
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(delay_seconds)
            except APIStatusError as exc:
                if exc.status_code not in _TRANSIENT_STATUS_CODES or attempt == 2:
                    raise
                delay_seconds = 2**attempt
                logger.warning(
                    "Azure AI Foundry returned status %s on attempt %s/3",
                    exc.status_code,
                    attempt + 1,
                )
                await asyncio.sleep(delay_seconds)

        raise RuntimeError("Failed to generate embedding after retries")

    async def close(self) -> None:
        if self._openai_client is not None:
            close_method = getattr(self._openai_client, "close", None)
            if close_method is not None:
                close_result = close_method()
                if inspect.isawaitable(close_result):
                    await close_result
            self._openai_client = None

        if self._project_client is not None:
            await self._project_client.close()
            self._project_client = None

        if self._credential is not None and self._owns_credential:
            await self._credential.close()
            self._credential = None

    async def _get_openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            credential = self._credential
            if credential is None:
                credential = DefaultAzureCredential()
                self._credential = credential
                self._owns_credential = True

            self._project_client = self._project_client_factory(
                endpoint=self._project_endpoint,
                credential=credential,
            )
            self._openai_client = self._project_client.get_openai_client()

        return self._openai_client

    @staticmethod
    def _build_project_endpoint(endpoint: str, project_name: str) -> str:
        normalized_endpoint = endpoint.rstrip("/")
        if not normalized_endpoint:
            raise ValueError("AZURE_AI_FOUNDRY_ENDPOINT must be configured")
        if "/api/projects/" in normalized_endpoint:
            return normalized_endpoint
        if not project_name:
            raise ValueError(
                "AZURE_AI_FOUNDRY_PROJECT must be configured when the "
                "endpoint does not include /api/projects/{project}"
            )
        return f"{normalized_endpoint}/api/projects/{project_name}"


def get_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """Create an embedding provider from configuration."""
    if config.provider == "fake":
        return FakeEmbeddingProvider(config)
    if config.provider == "azure_ai_foundry":
        return AzureAIFoundryEmbeddingProvider(config)
    raise ValueError(f"Unsupported embedding provider: {config.provider}")

"""Unit tests for Phase 5 embedding behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import EmbeddingConfig
from src.embeddings.batcher import batch_embed
from src.embeddings.provider import (AzureAIFoundryEmbeddingProvider,
                                     FakeEmbeddingProvider,
                                     get_embedding_provider)


@pytest.mark.asyncio
async def test_fake_embedding_provider_is_deterministic() -> None:
    config = EmbeddingConfig(provider="fake", fake_dimension=8)
    provider = FakeEmbeddingProvider(config)

    first = await provider.embed_text("deterministic text")
    second = await provider.embed_text("deterministic text")
    third = await provider.embed_text("other text")

    assert len(first) == 8
    assert first == second
    assert first != third
    assert all(-1.0 <= value <= 1.0 for value in first)


@pytest.mark.asyncio
async def test_get_embedding_provider_selects_fake_provider() -> None:
    provider = get_embedding_provider(
        EmbeddingConfig(provider="fake", fake_dimension=4)
    )

    assert isinstance(provider, FakeEmbeddingProvider)


@pytest.mark.asyncio
async def test_batch_embed_preserves_input_order() -> None:
    config = EmbeddingConfig(
        provider="fake",
        fake_dimension=3,
        batch_size=2,
        max_tokens_per_batch=4,
    )
    provider = FakeEmbeddingProvider(config)
    texts = ["a", "bb", "c" * 20]

    embeddings = await batch_embed(texts, provider, config)

    assert len(embeddings) == 3
    assert embeddings[0] == await provider.embed_text("a")
    assert embeddings[1] == await provider.embed_text("bb")
    assert embeddings[2] == await provider.embed_text("c" * 20)


class _FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def create(self, *, input: list[str], model: str) -> SimpleNamespace:
        self.calls.append((input, model))
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsClient()

    async def close(self) -> None:
        return None


class _FakeProjectClient:
    instances: list["_FakeProjectClient"] = []

    def __init__(self, *, endpoint: str, credential: object) -> None:
        self.endpoint = endpoint
        self.credential = credential
        self.openai_client = _FakeOpenAIClient()
        self.closed = False
        self.__class__.instances.append(self)

    def get_openai_client(self) -> _FakeOpenAIClient:
        return self.openai_client

    async def close(self) -> None:
        self.closed = True


class _FakeCredential:
    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_azure_foundry_provider_uses_projects_client() -> None:
    _FakeProjectClient.instances.clear()
    config = EmbeddingConfig(
        provider="azure_ai_foundry",
        azure_ai_foundry_project="demo-project",
        azure_ai_foundry_endpoint="https://example.services.ai.azure.com",
        azure_ai_foundry_deployment="text-embedding-3-large",
    )
    provider = AzureAIFoundryEmbeddingProvider(
        config,
        credential=_FakeCredential(),
        project_client_factory=_FakeProjectClient,
    )

    try:
        embedding = await provider.embed_text("hello")
    finally:
        await provider.close()

    assert embedding == [0.1, 0.2, 0.3]
    assert len(_FakeProjectClient.instances) == 1
    project_client = _FakeProjectClient.instances[0]
    assert (
        project_client.endpoint
        == "https://example.services.ai.azure.com/api/projects/demo-project"
    )
    assert project_client.openai_client.embeddings.calls == [
        (["hello"], "text-embedding-3-large")
    ]
    assert project_client.closed is True

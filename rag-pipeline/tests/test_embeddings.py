"""Unit tests for embedding provider selection and batching."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import EmbeddingConfig
from src.embeddings.batcher import _iter_batches, batch_embed
from src.embeddings.provider import (
    AzureAIFoundryEmbeddingProvider,
    FakeEmbeddingProvider,
    get_embedding_provider,
)


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [float(len(self.calls)), float(len(text))]


class FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def create(self, *, input: list[str], model: str) -> SimpleNamespace:
        self.calls.append((input, model))
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsClient()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeProjectClient:
    instances: list["FakeProjectClient"] = []

    def __init__(self, *, endpoint: str, credential: object) -> None:
        self.endpoint = endpoint
        self.credential = credential
        self.openai_client = FakeOpenAIClient()
        self.closed = False
        self.__class__.instances.append(self)

    def get_openai_client(self) -> FakeOpenAIClient:
        return self.openai_client

    async def close(self) -> None:
        self.closed = True


class FakeCredential:
    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_get_embedding_provider_selects_fake_provider() -> None:
    provider = get_embedding_provider(
        EmbeddingConfig(provider="fake", fake_dimension=4)
    )

    assert isinstance(provider, FakeEmbeddingProvider)


@pytest.mark.asyncio
async def test_get_embedding_provider_selects_azure_foundry_provider() -> None:
    provider = get_embedding_provider(
        EmbeddingConfig(
            provider="azure_ai_foundry",
            azure_ai_foundry_endpoint="https://example.services.ai.azure.com",
            azure_ai_foundry_project="demo-project",
            azure_ai_foundry_deployment="text-embedding-3-large",
        )
    )

    assert isinstance(provider, AzureAIFoundryEmbeddingProvider)
    await provider.close()


@pytest.mark.asyncio
async def test_fake_embeddings_are_deterministic_and_have_expected_dimension() -> None:
    provider = FakeEmbeddingProvider(EmbeddingConfig(provider="fake", fake_dimension=6))

    first = await provider.embed_text("same text")
    second = await provider.embed_text("same text")

    assert first == second
    assert len(first) == 6
    assert all(-1.0 <= value <= 1.0 for value in first)


@pytest.mark.asyncio
async def test_batch_embed_respects_batch_size_and_token_limit() -> None:
    config = EmbeddingConfig(
        provider="fake",
        fake_dimension=3,
        batch_size=2,
        max_tokens_per_batch=5,
    )
    texts = ["a" * 4, "b" * 16, "c" * 4, "d" * 24]

    batches = list(_iter_batches(texts, config.batch_size, config.max_tokens_per_batch))

    assert batches == [[texts[0], texts[1]], [texts[2]], [texts[3]]]


@pytest.mark.asyncio
async def test_batch_embed_returns_results_in_input_order() -> None:
    provider = RecordingProvider()
    config = EmbeddingConfig(provider="fake", fake_dimension=2, batch_size=2)
    texts = ["alpha", "beta", "gamma"]

    embeddings = await batch_embed(texts, provider, config)

    assert provider.calls == texts
    assert embeddings == [[1.0, 5.0], [2.0, 4.0], [3.0, 5.0]]


@pytest.mark.asyncio
async def test_azure_foundry_provider_uses_mocked_projects_client() -> None:
    FakeProjectClient.instances.clear()
    provider = AzureAIFoundryEmbeddingProvider(
        EmbeddingConfig(
            provider="azure_ai_foundry",
            azure_ai_foundry_endpoint="https://example.services.ai.azure.com",
            azure_ai_foundry_project="demo-project",
            azure_ai_foundry_deployment="text-embedding-3-large",
        ),
        credential=FakeCredential(),
        project_client_factory=FakeProjectClient,
    )

    try:
        embedding = await provider.embed_text("hello")
    finally:
        await provider.close()

    assert embedding == [0.1, 0.2, 0.3]
    assert len(FakeProjectClient.instances) == 1
    client = FakeProjectClient.instances[0]
    assert (
        client.endpoint
        == "https://example.services.ai.azure.com/api/projects/demo-project"
    )
    assert client.openai_client.embeddings.calls == [
        (["hello"], "text-embedding-3-large")
    ]
    assert client.closed is True
    assert client.openai_client.closed is True

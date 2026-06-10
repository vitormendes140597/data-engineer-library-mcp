"""Embedding provider exports."""

from src.embeddings.batcher import batch_embed
from src.embeddings.provider import (AzureAIFoundryEmbeddingProvider,
                                     EmbeddingProvider, FakeEmbeddingProvider,
                                     get_embedding_provider)

__all__ = [
    "AzureAIFoundryEmbeddingProvider",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "batch_embed",
    "get_embedding_provider",
]

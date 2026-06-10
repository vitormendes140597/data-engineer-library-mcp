"""Batch embedding helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable

from src.config import EmbeddingConfig
from src.embeddings.provider import EmbeddingProvider


async def batch_embed(
    texts: list[str],
    provider: EmbeddingProvider,
    config: EmbeddingConfig,
) -> list[list[float]]:
    """Embed texts in batches while preserving input order."""
    embeddings: list[list[float]] = []
    for batch in _iter_batches(texts, config.batch_size, config.max_tokens_per_batch):
        for text in batch:
            embeddings.append(await provider.embed_text(text))
    return embeddings


def _iter_batches(
    texts: list[str],
    batch_size: int,
    max_tokens_per_batch: int,
) -> Iterable[list[str]]:
    normalized_batch_size = max(1, batch_size)
    normalized_max_tokens = max(1, max_tokens_per_batch)

    batch: list[str] = []
    batch_tokens = 0

    for text in texts:
        text_tokens = _estimate_tokens(text)
        exceeds_batch_size = len(batch) >= normalized_batch_size
        exceeds_token_limit = (
            bool(batch) and batch_tokens + text_tokens > normalized_max_tokens
        )

        if exceeds_batch_size or exceeds_token_limit:
            yield batch
            batch = []
            batch_tokens = 0

        batch.append(text)
        batch_tokens += text_tokens

        if text_tokens > normalized_max_tokens:
            yield batch
            batch = []
            batch_tokens = 0

    if batch:
        yield batch


def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))

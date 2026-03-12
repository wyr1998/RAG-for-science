"""
Zhipu Embedding-3 backend. Uses zhipuai SDK; API key via ZHIPUAI_API_KEY or config.
"""

from __future__ import annotations

import os
from typing import Any

from ..embedding_interface import EmbeddingBackendBase, register_backend


@register_backend("zhipu_embedding3")
class ZhipuEmbedding3Backend(EmbeddingBackendBase):
    """Zhipu Embedding-3. dimension configurable via `dimensions` (default 1024)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "embedding-3",
        dimensions: int = 1024,
        **kwargs: Any,
    ):
        self._api_key = api_key or os.environ.get("ZHIPUAI_API_KEY", "")
        self._model = model
        self._dimensions = dimensions
        self._kwargs = kwargs
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise ValueError(
                    "Zhipu API key required: set ZHIPUAI_API_KEY or pass api_key in config."
                )
            from zhipuai import ZhipuAI

            self._client = ZhipuAI(
                api_key=self._api_key,
                **{k: v for k, v in self._kwargs.items() if k in ("base_url", "timeout", "max_retries")},
            )
        return self._client

    @property
    def dimension(self) -> int:
        return self._dimensions

    @property
    def name(self) -> str:
        return "zhipu_embedding3"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Empty string -> use space so API accepts; we'll replace with zero vector after
        normalized = [t.strip() if t and t.strip() else " " for t in texts]
        client = self._get_client()
        zero = [0.0] * self._dimensions
        out: list[list[float]] = []
        # Batch to avoid token limits; Zhipu may accept list input
        batch_size = 20
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            # Zhipu embeddings.create currently does not accept a `dimensions` arg.
            resp = client.embeddings.create(
                model=self._model,
                input=batch,
            )
            for j, item in enumerate(resp.data):
                vec = list(item.embedding)
                # Restore zero vector for originally empty text
                idx = i + j
                if not (texts[idx] and texts[idx].strip()):
                    vec = zero
                out.append(vec)
        return out

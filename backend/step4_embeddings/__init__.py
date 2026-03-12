"""Step 4: Modular embedding interface and backends."""

from step4_embeddings.embedding_interface import (
    EmbeddingBackend,
    EmbeddingBackendBase,
    get_backend,
    list_backends,
    register_backend,
)

__all__ = [
    "EmbeddingBackend",
    "EmbeddingBackendBase",
    "get_backend",
    "list_backends",
    "register_backend",
]

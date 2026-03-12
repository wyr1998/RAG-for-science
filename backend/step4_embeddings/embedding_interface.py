"""
Modular embedding interface for the knowledge-base pipeline.
Implement EmbeddingBackend to add a new provider; switch via --backend or config.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Protocol for embedding backends. Implement embed_texts() and dimension."""

    @property
    def dimension(self) -> int:
        """Return embedding vector size."""
        ...

    @property
    def name(self) -> str:
        """Backend identifier (e.g. 'zhipu_embedding3')."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts. Returns list of vectors (each list[float]).
        Empty strings may be mapped to zero vector or skipped per backend.
        """
        ...


class EmbeddingBackendBase(ABC):
    """Abstract base for backends; use this if you want default helpers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


# Registry: name -> (factory or class). Factory has signature (config: dict) -> EmbeddingBackend.
_BACKENDS: dict[str, type] = {}


def register_backend(name: str):
    """Decorator to register an EmbeddingBackend class under a name."""

    def _register(cls: type):
        _BACKENDS[name] = cls
        return cls

    return _register


def get_backend(name: str, config: dict | None = None) -> EmbeddingBackend:
    """Get a backend by name. config is passed to the backend constructor."""
    config = config or {}
    if name not in _BACKENDS:
        raise ValueError(
            f"Unknown embedding backend: {name}. Available: {list(_BACKENDS.keys())}"
        )
    return _BACKENDS[name](**config)


def list_backends() -> list[str]:
    """Return registered backend names."""
    return list(_BACKENDS.keys())

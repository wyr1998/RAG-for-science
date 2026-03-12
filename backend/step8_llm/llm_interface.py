"""
Modular LLM interface for the knowledge-base pipeline.
Implement LLMBackend to add a new provider; switch via config file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    """Protocol for LLM backends. Implement answer(query, context_text) -> str."""

    @property
    def name(self) -> str:
        """Backend identifier (e.g. 'zhipu')."""
        ...

    def answer(self, query: str, context_text: str) -> str:
        """
        Answer the query using the provided context text.
        Returns the model's reply as plain text.
        """
        ...


class LLMBackendBase(ABC):
    """Abstract base for LLM backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def answer(self, query: str, context_text: str) -> str:
        ...


_BACKENDS: dict[str, type] = {}


def register_llm(name: str):
    """Decorator to register an LLMBackend class under a name."""

    def _register(cls: type):
        _BACKENDS[name] = cls
        return cls

    return _register


def get_llm_backend(name: str, config: dict | None = None) -> LLMBackend:
    """Get a backend by name. config is passed to the backend constructor."""
    config = config or {}
    if name not in _BACKENDS:
        raise ValueError(
            f"Unknown LLM backend: {name}. Available: {list(_BACKENDS.keys())}"
        )
    return _BACKENDS[name](**config)


def list_llm_backends() -> list[str]:
    """Return registered LLM backend names."""
    return list(_BACKENDS.keys())

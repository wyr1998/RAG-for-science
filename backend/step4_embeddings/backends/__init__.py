"""Embedding backends. Import to register with the interface."""

from .zhipu_embedding3 import ZhipuEmbedding3Backend

__all__ = ["ZhipuEmbedding3Backend"]

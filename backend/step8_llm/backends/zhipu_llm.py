"""
Zhipu (智谱) LLM backend. Uses zhipuai SDK; API key via env var named in config.
"""

from __future__ import annotations

import os
from typing import Any

from ..llm_interface import LLMBackendBase, register_llm


@register_llm("zhipu")
class ZhipuLLMBackend(LLMBackendBase):
    """Zhipu chat (e.g. glm-4). API key: pass api_key in config, or set env var named by api_key_env."""

    def __init__(
        self,
        model: str = "glm-4",
        api_key: str | None = None,
        api_key_env: str = "ZHIPUAI_API_KEY",
        **kwargs: Any,
    ):
        self._model = model
        self._api_key = api_key
        self._api_key_env = api_key_env
        self._kwargs = kwargs

    @property
    def name(self) -> str:
        return "zhipu"

    def answer(self, query: str, context_text: str) -> str:
        api_key = self._api_key or os.environ.get(self._api_key_env)
        if not api_key:
            raise RuntimeError(
                "Zhipu API key required: set api_key in config or set environment variable "
                f"named by api_key_env (default: ZHIPUAI_API_KEY)."
            )
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)

        system_prompt = (
            "You are an expert assistant helping with questions about scientific papers.\n"
            "Use ONLY the provided context to answer. If the context is insufficient, "
            "say that you are not sure.\n"
            "When figures are relevant, mention their figure numbers or descriptions "
            "based on the figure captions in the context."
        )
        user_content = (
            f"Question:\n{query}\n\n"
            f"Context from retrieved papers:\n{context_text}\n\n"
            "Please provide a concise, well-structured answer."
        )

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            **{k: v for k, v in self._kwargs.items() if k in ("temperature", "max_tokens")},
        )
        choice = response.choices[0]
        return choice.message.content if hasattr(choice, "message") else str(response)

"""Model-agnostic client for an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import os
from collections.abc import Sequence
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit

from xhotpotqa.generation.config import GenerationConfig


class OpenAICompatibleGenerator:
    """A lazy, credential-safe adapter for an OpenAI-compatible chat endpoint."""

    def __init__(self, config: GenerationConfig, *, client: Any | None = None) -> None:
        if config.backend != "openai_compatible":
            raise ValueError("Expected backend=openai_compatible")
        self._config = config
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            base_url, api_key = _connection_settings(self._config)
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    'Install generation dependencies with pip install -e ".[generation]"'
                ) from error
            self._client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=self._config.timeout_seconds,
                max_retries=self._config.http_max_retries,
            )
        return self._client

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        request_messages = _validate_messages(messages)
        client = self._get_client()
        request: dict[str, Any] = {
            "model": self._config.model_id,
            "messages": request_messages,
            "max_tokens": self._config.max_new_tokens,
            "temperature": self._config.temperature,
            "top_p": self._config.top_p,
            "seed": self._config.seed,
            "response_format": {"type": "json_object"},
        }
        if self._config.chat_template_kwargs:
            request["extra_body"] = {
                "chat_template_kwargs": dict(self._config.chat_template_kwargs)
            }
        response = client.chat.completions.create(**request)
        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError("vLLM returned no completion choices")
        choice = choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ValueError("vLLM truncated the response at max_new_tokens")
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("vLLM returned an empty assistant message")
        return content.strip()


def _connection_settings(config: GenerationConfig) -> tuple[str, str]:
    raw_base_url = os.environ.get(config.base_url_env, "").strip()
    if not raw_base_url:
        raise RuntimeError(f"Set {config.base_url_env}, for example http://localhost:8000/v1")
    parsed = urlsplit(raw_base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"{config.base_url_env} must be an http(s) URL without credentials, query, or fragment"
        )
    api_key = os.environ.get(config.api_key_env, "").strip()
    if not api_key:
        if not _is_loopback(parsed.hostname):
            raise RuntimeError(
                f"Set {config.api_key_env}; placeholder credentials are allowed only "
                "for loopback URLs"
            )
        api_key = "EMPTY"
    return raw_base_url.rstrip("/"), api_key


def _is_loopback(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validate_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    if not messages:
        raise ValueError("At least one chat message is required")
    validated: list[dict[str, str]] = []
    allowed_roles = {"system", "developer", "user", "assistant"}
    for index, message in enumerate(messages):
        role = message.get("role")
        content = message.get("content")
        if role not in allowed_roles:
            raise ValueError(f"Message {index} has an unsupported role")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Message {index} must have non-empty string content")
        validated.append({"role": role, "content": content})
    return validated

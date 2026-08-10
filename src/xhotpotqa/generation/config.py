"""Generation configuration with explicit, reproducible defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_ENVIRONMENT_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    model_id: str
    revision: str = "main"
    backend: str = "openai_compatible"
    base_url_env: str = "OPENAI_BASE_URL"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: float = 180.0
    http_max_retries: int = 2
    seed: int = 20260810
    enable_thinking: bool = False
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0
    max_new_tokens: int = 2048
    max_retries: int = 3
    checkpoint_every: int = 25

    def __post_init__(self) -> None:
        if self.backend != "openai_compatible":
            raise ValueError("backend must be 'openai_compatible'")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id must be non-empty")
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError("revision must be non-empty")
        for field_name, value in (
            ("base_url_env", self.base_url_env),
            ("api_key_env", self.api_key_env),
        ):
            if not isinstance(value, str) or not _ENVIRONMENT_VARIABLE.fullmatch(value):
                raise ValueError(f"{field_name} is not a valid environment-variable name")
        if self.base_url_env == self.api_key_env:
            raise ValueError("base_url_env and api_key_env must be different")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be greater than zero")
        _require_integer("http_max_retries", self.http_max_retries, minimum=0)
        _require_integer("seed", self.seed, minimum=0)
        _require_integer("max_new_tokens", self.max_new_tokens, minimum=1)
        _require_integer("max_retries", self.max_retries, minimum=1)
        _require_integer("checkpoint_every", self.checkpoint_every, minimum=1)
        _require_boolean("enable_thinking", self.enable_thinking)
        _require_boolean("do_sample", self.do_sample)
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not 0.0 <= self.temperature <= 2.0
        ):
            raise ValueError("temperature must be between 0 and 2")
        if (
            isinstance(self.top_p, bool)
            or not isinstance(self.top_p, (int, float))
            or not 0.0 < self.top_p <= 1.0
        ):
            raise ValueError("top_p must be in the interval (0, 1]")
        if not self.do_sample and (self.temperature != 0.0 or self.top_p != 1.0):
            raise ValueError("deterministic decoding requires temperature=0 and top_p=1")

    def decoding_parameters(self) -> dict[str, bool | float | int]:
        """Return the exact request-time decoding parameters for provenance."""
        return {
            "enable_thinking": self.enable_thinking,
            "do_sample": self.do_sample,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
            "max_new_tokens": self.max_new_tokens,
        }

    @classmethod
    def from_yaml(cls, path: Path) -> GenerationConfig:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
            raise ValueError(f"Expected a YAML mapping in {path}")
        payload = cast(dict[str, Any], loaded)
        try:
            return cls(**payload)
        except TypeError as error:
            raise ValueError(f"Invalid generation configuration in {path}: {error}") from error


def _require_integer(name: str, value: object, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")


def _require_boolean(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")

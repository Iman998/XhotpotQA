from types import SimpleNamespace
from typing import Any

import pytest

from xhotpotqa.generation.config import GenerationConfig
from xhotpotqa.generation.openai_compatible import (
    OpenAICompatibleGenerator,
    _connection_settings,
)


class RecordingCompletions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: object) -> None:
        self.chat = SimpleNamespace(completions=RecordingCompletions(response))


def completion(content: object, *, finish_reason: str = "stop") -> object:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
        ]
    )


def test_request_matches_deterministic_vllm_contract() -> None:
    client = FakeClient(completion(' {"translation":"سلام"} '))
    config = GenerationConfig(model_id="served-translation-model")
    generator = OpenAICompatibleGenerator(config, client=client)

    result = generator.generate([{"role": "user", "content": "translate"}])

    assert result == '{"translation":"سلام"}'
    request = client.chat.completions.calls[0]
    assert request["model"] == config.model_id
    assert request["temperature"] == 0.0
    assert request["top_p"] == 1.0
    assert request["seed"] == config.seed
    assert request["response_format"] == {"type": "json_object"}
    assert "extra_body" not in request


def test_optional_chat_template_kwargs_are_forwarded_without_model_assumptions() -> None:
    client = FakeClient(completion('{"translation":"hello"}'))
    config = GenerationConfig(
        model_id="served-translation-model",
        chat_template_kwargs={"enable_custom_mode": False},
    )

    OpenAICompatibleGenerator(config, client=client).generate(
        [{"role": "user", "content": "translate"}]
    )

    assert client.chat.completions.calls[0]["extra_body"] == {
        "chat_template_kwargs": {"enable_custom_mode": False}
    }


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (SimpleNamespace(choices=[]), "no completion choices"),
        (completion(None), "empty assistant message"),
        (completion("{}", finish_reason="length"), "truncated"),
    ],
)
def test_invalid_or_truncated_completion_is_rejected(response: object, message: str) -> None:
    generator = OpenAICompatibleGenerator(
        GenerationConfig(model_id="model"), client=FakeClient(response)
    )

    with pytest.raises(ValueError, match=message):
        generator.generate([{"role": "user", "content": "request"}])


def test_invalid_message_is_rejected_before_request() -> None:
    client = FakeClient(completion("{}"))
    generator = OpenAICompatibleGenerator(GenerationConfig(model_id="model"), client=client)

    with pytest.raises(ValueError, match="unsupported role"):
        generator.generate([{"role": "tool", "content": "untrusted"}])

    assert client.chat.completions.calls == []


def test_local_endpoint_may_use_placeholder_key(monkeypatch: pytest.MonkeyPatch) -> None:
    config = GenerationConfig(model_id="model")
    monkeypatch.setenv(config.base_url_env, "http://127.0.0.1:8000/v1/")
    monkeypatch.delenv(config.api_key_env, raising=False)

    assert _connection_settings(config) == ("http://127.0.0.1:8000/v1", "EMPTY")


def test_remote_endpoint_requires_explicit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    config = GenerationConfig(model_id="model")
    monkeypatch.setenv(config.base_url_env, "https://example.test/v1")
    monkeypatch.delenv(config.api_key_env, raising=False)

    with pytest.raises(RuntimeError, match=config.api_key_env):
        _connection_settings(config)


def test_url_must_not_embed_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    config = GenerationConfig(model_id="model")
    monkeypatch.setenv(config.base_url_env, "https://user:secret@example.test/v1")

    with pytest.raises(RuntimeError, match="without credentials"):
        _connection_settings(config)

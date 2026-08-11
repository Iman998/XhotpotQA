from pathlib import Path

import pytest

from xhotpotqa.generation.config import GenerationConfig


def test_reference_config_loads_and_records_exact_decoding() -> None:
    config = GenerationConfig.from_yaml(Path("configs/generation/openai_compatible.yaml"))

    assert config.model_id == "served-translation-model"
    assert config.http_max_retries == 2
    assert config.decoding_parameters() == {
        "chat_template_kwargs": {},
        "do_sample": False,
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 20260810,
        "max_new_tokens": 2048,
    }


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"model_id": ""}, "model_id"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"http_max_retries": -1}, "http_max_retries"),
        ({"max_retries": 0}, "max_retries"),
        ({"do_sample": "false"}, "do_sample"),
        ({"chat_template_kwargs": []}, "chat_template_kwargs"),
        ({"chat_template_kwargs": {"nested": {"value": True}}}, "scalar JSON"),
        ({"temperature": True}, "temperature"),
        ({"top_p": 0}, "top_p"),
        ({"temperature": 0.5}, "deterministic decoding"),
        ({"base_url_env": "not-valid!"}, "base_url_env"),
    ],
)
def test_invalid_configuration_is_rejected(override: dict[str, object], message: str) -> None:
    values: dict[str, object] = {"model_id": "model"}
    values.update(override)

    with pytest.raises(ValueError, match=message):
        GenerationConfig(**values)  # type: ignore[arg-type]


def test_yaml_root_must_be_a_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML mapping"):
        GenerationConfig.from_yaml(config_path)

import json
from dataclasses import replace
from pathlib import Path

import pytest

from xhotpotqa.cli import main
from xhotpotqa.data.checksum import compute_checksum, with_checksum
from xhotpotqa.data.io import canonical_json, read_instances, write_instances
from xhotpotqa.data.models import (
    CandidateParagraph,
    Provenance,
    SupportingFact,
    XHotpotInstance,
)
from xhotpotqa.data.plus import (
    LANGUAGES_PER_INSTANCE,
    QATranslation,
    expand_instance,
    expand_instances,
    load_qa_translations,
    variant_id,
    write_plus_instances,
)
from xhotpotqa.languages import LANGUAGE_CODES


def _base(source_id: str = "source-1") -> XHotpotInstance:
    return with_checksum(
        XHotpotInstance(
            id=f"xhp-validation-{source_id}",
            source_id=source_id,
            source_split="validation",
            question="Who wrote the program?",
            answer="Ada Lovelace",
            question_language="en",
            answer_language="en",
            candidates=(
                CandidateParagraph(
                    id="p00",
                    title="Analytical Engine",
                    sentences=("Ada described an algorithm.",),
                    language="de",
                    source_title="Analytical Engine",
                    source_sentences=("Ada described an algorithm.",),
                ),
                CandidateParagraph(
                    id="p01",
                    title="Charles Babbage",
                    sentences=("Babbage designed the engine.",),
                    language="fa",
                    source_title="Charles Babbage",
                    source_sentences=("Babbage designed the engine.",),
                ),
            ),
            supporting_facts=(
                SupportingFact("p00", 0, "answer"),
                SupportingFact("p01", 0, "bridge"),
            ),
            question_type="bridge",
            difficulty="hard",
            provenance=Provenance(
                assignment_version="sha256-hash-v1",
                seed=17,
                translation_model="translator",
                translation_revision="revision",
                prompt_version="prompt-v1",
                created_at="2026-08-10T00:00:00+00:00",
                decoding={"temperature": 0},
            ),
        )
    )


def _translations(source_id: str = "source-1") -> dict[str, QATranslation]:
    return {
        language: QATranslation(
            question=f"question:{source_id}:{language}",
            answer=f"answer:{source_id}:{language}",
        )
        for language in LANGUAGE_CODES
    }


def _json_translation_payload(source_id: str) -> dict[str, dict[str, dict[str, str]]]:
    return {
        source_id: {
            language: {
                "question": f"question:{source_id}:{language}",
                "answer": f"answer:{source_id}:{language}",
            }
            for language in LANGUAGE_CODES
        }
    }


def test_expand_instance_is_deterministic_and_holds_evidence_fixed() -> None:
    base = _base()
    first = expand_instance(base, _translations())
    second = expand_instance(base, _translations())

    assert first == second
    assert len(first) == LANGUAGES_PER_INSTANCE == 24
    assert tuple(item.question_language for item in first) == LANGUAGE_CODES
    assert len({item.id for item in first}) == LANGUAGES_PER_INSTANCE
    for language, variant in zip(LANGUAGE_CODES, first, strict=True):
        assert variant.id == variant_id(base.id, language)
        assert variant.source_id == base.source_id
        assert variant.answer_language == language
        assert variant.candidates == base.candidates
        assert variant.supporting_facts == base.supporting_facts
        assert variant.question_type == base.question_type
        assert variant.difficulty == base.difficulty
        assert variant.provenance == base.provenance
        assert variant.checksum == compute_checksum(variant)


def test_expansion_requires_every_language_and_valid_base_checksum() -> None:
    translations = _translations()
    translations.pop("sv")
    with pytest.raises(ValueError, match="exactly 24 languages"):
        expand_instance(_base(), translations)

    translations = _translations()
    translations["xx"] = QATranslation("question", "answer")
    with pytest.raises(ValueError, match=r"extra=\['xx'\]"):
        expand_instance(_base(), translations)

    broken_base = replace(_base(), question="changed after checksum")
    with pytest.raises(ValueError, match="invalid checksum"):
        expand_instance(broken_base, _translations())


def test_expand_instances_rejects_missing_extra_and_duplicate_sources() -> None:
    with pytest.raises(ValueError, match="Missing translations"):
        list(expand_instances([_base()], {}))

    mappings = {"source-1": _translations(), "unused": _translations("unused")}
    with pytest.raises(ValueError, match="no matching base source ID"):
        list(expand_instances([_base()], mappings))

    duplicate = replace(_base(), id="different-id")
    with pytest.raises(ValueError, match="Duplicate base source ID"):
        list(expand_instances([_base(), duplicate], {"source-1": _translations()}))


def test_translation_loader_accepts_source_keyed_json_and_jsonl(tmp_path: Path) -> None:
    source_id = "source-1"
    json_path = tmp_path / "translations.json"
    json_path.write_text(
        json.dumps(_json_translation_payload(source_id), ensure_ascii=False), encoding="utf-8"
    )
    from_json = load_qa_translations(json_path)
    assert tuple(from_json[source_id]) == LANGUAGE_CODES

    jsonl_path = tmp_path / "translations.jsonl"
    row = {
        "source_id": source_id,
        "translations": _json_translation_payload(source_id)[source_id],
    }
    jsonl_path.write_text(canonical_json(row) + "\n", encoding="utf-8")
    assert load_qa_translations(jsonl_path) == from_json


def test_atomic_writer_keeps_existing_output_after_validation_failure(tmp_path: Path) -> None:
    output = tmp_path / "plus.jsonl"
    output.write_text("previous release\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected 2 base records"):
        write_plus_instances(
            output,
            [_base()],
            {"source-1": _translations()},
            expected_base_count=2,
            expected_split="validation",
        )

    assert output.read_text(encoding="utf-8") == "previous release\n"
    assert not list(tmp_path.glob(".plus.jsonl.*.tmp"))


def test_expand_plus_cli_writes_24_valid_variants(tmp_path: Path) -> None:
    base_path = tmp_path / "base.jsonl"
    translations_path = tmp_path / "translations.json"
    output_path = tmp_path / "plus.jsonl"
    write_instances(base_path, [_base()])
    translations_path.write_text(
        json.dumps(_json_translation_payload("source-1"), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "expand-plus",
            "--base",
            str(base_path),
            "--translations",
            str(translations_path),
            "--output",
            str(output_path),
            "--split",
            "validation",
        ]
    )

    variants = list(read_instances(output_path))
    assert exit_code == 0
    assert len(variants) == LANGUAGES_PER_INSTANCE
    assert all(item.checksum == compute_checksum(item) for item in variants)

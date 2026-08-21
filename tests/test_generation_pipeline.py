import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from xhotpotqa.data.assignment import MANIFEST_SCHEMA_VERSION, ManifestLanguageAssigner
from xhotpotqa.generation.pipeline import XHotpotBuilder
from xhotpotqa.generation.protocols import TranslationStats


class PassthroughTranslator:
    model_id = "served-model"
    revision = "immutable-revision"
    decoding: Mapping[str, object] = {"temperature": 0.0}

    @contextmanager
    def record_scope(self) -> Iterator[TranslationStats]:
        yield TranslationStats()

    def translate_text(self, text: str, target_language: str, unit: str) -> str:
        return f"{target_language}:{text}"

    def translate_sentences(
        self, sentences: Sequence[str], target_language: str
    ) -> tuple[str, ...]:
        return tuple(f"{target_language}:{sentence}" for sentence in sentences)


def test_builder_records_manifest_identity_and_replays_v1_assignment(tmp_path: Path) -> None:
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "assignment_version": "xhotpotqa-v1-preserved-v2",
        "assignments": {
            "source-1": {
                "question-answer": "fa",
                "paragraph:0": "en",
                "paragraph:1": "de",
            }
        },
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    manifest = tmp_path / "assignments.json"
    manifest.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    builder = XHotpotBuilder(
        PassthroughTranslator(),
        ManifestLanguageAssigner.from_path(manifest),
    )
    source = {
        "_id": "source-1",
        "question": "Question?",
        "answer": "Answer",
        "context": [
            ["First", ["Sentence one."]],
            ["Second", ["Sentence two."]],
        ],
        "supporting_facts": [["First", 0], ["Second", 0]],
        "type": "bridge",
        "level": "hard",
    }

    instance = builder.build(source, "validation")

    assert instance.question_language == "fa"
    assert instance.answer_language == "fa"
    assert [candidate.language for candidate in instance.candidates] == ["en", "de"]
    assert instance.provenance.assignment_version == "xhotpotqa-v1-preserved-v2"
    assert instance.provenance.assignment_manifest_sha256 == digest
    assert instance.provenance.seed is None
    assert builder.resume_signature["assignment_manifest_sha256"] == digest

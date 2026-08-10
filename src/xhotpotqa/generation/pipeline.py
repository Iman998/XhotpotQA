"""Pure transformation from a HotpotQA record to one XHotpotQA instance."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from xhotpotqa.data.assignment import LanguageAssigner
from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.models import (
    CandidateParagraph,
    Provenance,
    SupportingFact,
    XHotpotInstance,
)
from xhotpotqa.generation.protocols import TranslationService
from xhotpotqa.generation.translation import PROMPT_HASH, PROMPT_VERSION


class XHotpotBuilder:
    def __init__(self, translator: TranslationService, assigner: LanguageAssigner) -> None:
        self._translator = translator
        self._assigner = assigner

    @property
    def resume_signature(self) -> dict[str, object]:
        """Return immutable settings that must match before resuming output."""
        return {
            "assignment_version": "sha256-hash-v1",
            "seed": self._assigner.seed,
            "translation_model": self._translator.model_id,
            "translation_revision": self._translator.revision,
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": PROMPT_HASH,
            "decoding": dict(self._translator.decoding),
        }

    def build(self, source: Mapping[str, Any], source_split: str) -> XHotpotInstance:
        source_id = str(source.get("_id", source.get("id", "")))
        if not source_id:
            raise ValueError("HotpotQA source record is missing _id/id")
        retries_before = int(getattr(self._translator, "retry_count", 0))
        question_language = self._assigner.assign(source_id, "question-answer")
        question = self._translator.translate_text(
            str(source["question"]), question_language, "question"
        )
        answer = self._translator.translate_text(str(source["answer"]), question_language, "answer")

        candidates: list[CandidateParagraph] = []
        source_title_to_ids: dict[str, list[str]] = {}
        for index, raw_candidate in enumerate(source["context"]):
            source_title, source_sentences = raw_candidate
            paragraph_id = f"p{index:02d}"
            language = self._assigner.assign(source_id, f"paragraph:{index}")
            title = self._translator.translate_text(str(source_title), language, "title")
            sentences = self._translator.translate_sentences(tuple(source_sentences), language)
            candidates.append(
                CandidateParagraph(
                    id=paragraph_id,
                    title=title,
                    sentences=sentences,
                    language=language,
                    source_title=str(source_title),
                    source_sentences=tuple(source_sentences),
                )
            )
            source_title_to_ids.setdefault(str(source_title), []).append(paragraph_id)

        supporting_facts = tuple(
            SupportingFact(
                paragraph_id=_resolve_paragraph_id(source_title_to_ids, str(title)),
                sentence_id=int(sentence_id),
            )
            for title, sentence_id in source["supporting_facts"]
        )
        provenance = Provenance(
            assignment_version="sha256-hash-v1",
            seed=self._assigner.seed,
            translation_model=self._translator.model_id,
            translation_revision=self._translator.revision,
            prompt_version=PROMPT_VERSION,
            prompt_hash=PROMPT_HASH,
            retry_count=int(getattr(self._translator, "retry_count", 0)) - retries_before,
            created_at=datetime.now(timezone.utc).isoformat(),
            validation_status="structural-passed",
            decoding=dict(self._translator.decoding),
        )
        instance = XHotpotInstance(
            id=f"xhp-{source_split}-{source_id}",
            source_id=source_id,
            source_split=source_split,
            question=question,
            answer=answer,
            question_language=question_language,
            answer_language=question_language,
            candidates=tuple(candidates),
            supporting_facts=supporting_facts,
            question_type=str(source.get("type", "unknown")),
            difficulty=str(source.get("level", "unknown")),
            provenance=provenance,
        )
        instance.validate()
        return with_checksum(instance)


def _resolve_paragraph_id(index: Mapping[str, list[str]], title: str) -> str:
    ids = index.get(title, [])
    if len(ids) != 1:
        raise ValueError(f"Supporting title {title!r} maps to {len(ids)} candidates")
    return ids[0]

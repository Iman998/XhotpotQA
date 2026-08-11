"""Typed canonical schema for XHotpotQA."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from xhotpotqa.languages import require_language

SupportRole = Literal["bridge", "answer", "comparison", "support"]


@dataclass(frozen=True, slots=True)
class CandidateParagraph:
    id: str
    title: str
    sentences: tuple[str, ...]
    language: str
    source_title: str | None = None
    source_sentences: tuple[str, ...] | None = None

    def validate(self) -> None:
        require_language(self.language)
        if not self.id or not self.title.strip():
            raise ValueError("Candidate id and title must be non-empty")
        if not self.sentences or any(not sentence.strip() for sentence in self.sentences):
            raise ValueError(f"Candidate {self.id!r} has empty sentence content")
        if self.source_sentences is not None and len(self.source_sentences) != len(self.sentences):
            raise ValueError(f"Candidate {self.id!r} changed sentence cardinality")


@dataclass(frozen=True, slots=True)
class SupportingFact:
    paragraph_id: str
    sentence_id: int
    role: SupportRole = "support"


@dataclass(frozen=True, slots=True)
class Provenance:
    schema_version: str = "xhotpotqa-record-v2"
    source_dataset: str = "hotpotqa/hotpot_qa"
    source_license: str = "CC-BY-SA-4.0"
    assignment_version: str = ""
    # Historical V1 assignments were sampled without a recorded seed.  ``None``
    # distinguishes that missing provenance from a genuine seed of zero.
    seed: int | None = None
    translation_model: str = ""
    translation_revision: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    retry_count: int = 0
    created_at: str = ""
    validation_status: str = ""
    decoding: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class XHotpotInstance:
    id: str
    source_id: str
    source_split: str
    question: str
    answer: str
    question_language: str
    answer_language: str
    candidates: tuple[CandidateParagraph, ...]
    supporting_facts: tuple[SupportingFact, ...]
    question_type: str = "unknown"
    difficulty: str = "unknown"
    provenance: Provenance = field(default_factory=Provenance)
    checksum: str = ""

    def validate(self) -> None:
        if not self.id or not self.source_id:
            raise ValueError("Instance and source IDs must be non-empty")
        if self.source_split not in {"train", "validation"}:
            raise ValueError(f"Instance {self.id!r} has an invalid source split")
        if not self.question.strip() or not self.answer.strip():
            raise ValueError(f"Instance {self.id!r} has an empty question or answer")
        require_language(self.question_language)
        require_language(self.answer_language)
        if self.question_language != self.answer_language:
            raise ValueError(f"Instance {self.id!r} violates question/answer language equality")
        if not self.candidates:
            raise ValueError(f"Instance {self.id!r} contains no candidates")
        paragraph_by_id = {candidate.id: candidate for candidate in self.candidates}
        if len(paragraph_by_id) != len(self.candidates):
            raise ValueError(f"Instance {self.id!r} contains duplicate candidate IDs")
        for candidate in self.candidates:
            candidate.validate()
        if not self.supporting_facts:
            raise ValueError(f"Instance {self.id!r} contains no supporting facts")
        if len(set(self.supporting_facts)) != len(self.supporting_facts):
            raise ValueError(f"Instance {self.id!r} contains duplicate supporting facts")
        for fact in self.supporting_facts:
            if fact.role not in {"bridge", "answer", "comparison", "support"}:
                raise ValueError(f"Instance {self.id!r} has an invalid supporting-fact role")
            if fact.paragraph_id not in paragraph_by_id:
                raise ValueError(f"Unknown supporting paragraph: {fact.paragraph_id!r}")
            sentence_count = len(paragraph_by_id[fact.paragraph_id].sentences)
            if not 0 <= fact.sentence_id < sentence_count:
                raise ValueError(
                    f"Supporting sentence {fact.sentence_id} is outside {fact.paragraph_id!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> XHotpotInstance:
        candidates = tuple(
            CandidateParagraph(
                id=item["id"],
                title=item["title"],
                sentences=tuple(item["sentences"]),
                language=item["language"],
                source_title=item.get("source_title"),
                source_sentences=(
                    tuple(item["source_sentences"])
                    if item.get("source_sentences") is not None
                    else None
                ),
            )
            for item in payload["candidates"]
        )
        facts = tuple(SupportingFact(**item) for item in payload["supporting_facts"])
        provenance = Provenance(**payload.get("provenance", {}))
        return cls(
            id=payload["id"],
            source_id=payload["source_id"],
            source_split=payload["source_split"],
            question=payload["question"],
            answer=payload["answer"],
            question_language=payload["question_language"],
            answer_language=payload["answer_language"],
            candidates=candidates,
            supporting_facts=facts,
            question_type=payload.get("question_type", "unknown"),
            difficulty=payload.get("difficulty", "unknown"),
            provenance=provenance,
            checksum=payload.get("checksum", ""),
        )

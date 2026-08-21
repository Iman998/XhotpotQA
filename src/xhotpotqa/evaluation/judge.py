"""Reproducible OpenAI-compatible LLM-as-a-judge evaluation."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit
from uuid import uuid4

from xhotpotqa.data.io import canonical_json, read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.languages import LANGUAGE_BY_CODE

JudgeUnit = Literal["paragraph", "question", "answer"]
JUDGE_UNIT_PARAGRAPH: Literal["paragraph"] = "paragraph"
JUDGE_UNIT_QUESTION: Literal["question"] = "question"
JUDGE_UNIT_ANSWER: Literal["answer"] = "answer"

SAMPLE_SCHEMA_VERSION = "xhotpotqa-judge-sample-v2"
RESULT_SCHEMA_VERSION = "xhotpotqa-judge-result-v2"
REPORT_SCHEMA_VERSION = "xhotpotqa-judge-report-v2"
JUDGE_PROMPT_VERSION = "xhotpotqa-translation-judge-v2.0"
LEGACY_JUDGE_PROMPT_VERSION = "xhotpotqa-translation-judge-legacy-v1"

# These two constants preserve the exact prompts used to create the historical
# GLM-labelled artifacts. New evaluations use the strict JSON v2 prompts below.
LEGACY_JUDGE_SYSTEM_PROMPT = """You are a meticulous bilingual translation judge. Your task is to assign a single integer score from 0 to 100 (0 = unusable, 100 = excellent) for a candidate translation, using only the source text and the target candidate.
Scoring rubric (decide internally; do not print sub-scores):
Adequacy/Faithfulness (60%): Candidate conveys all meaning from the source; no omissions/additions; no contradictions. Use your bilingual understanding to compare source meaning with the target text.
Terminology, Entities, Numbers (15%): Names, numbers, dates, units, and placeholders preserved and correct.
Fluency/Grammar (20%): Natural, grammatical writing in the target language.
Style/Register (5%): Tone/register appropriate to the source intent and genre.
Critical error floors:
Wrong language or untranslated copy of source -> <=10
Direct contradiction/mistranslation of key meaning -> <=40
Hallucinated content not grounded in source -> <=40
Loss/corruption of critical numbers, names, or placeholders -> <=60
Guidance: Favor semantic fidelity to the source over cleverness. Do not invent facts. Minor orthographic or punctuation quirks are minor unless they change meaning.
Round to the nearest integer and clamp to [0,100]. If inputs are empty or unusable, return 0.

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100."""  # noqa: E501

LEGACY_JUDGE_ANSWER_SYSTEM_PROMPT = """You are a meticulous bilingual translation judge for short answers. You are given an English question ("context_question") and its short English answer ("text") alongside a translated answer ("model_output"). Your task is to judge how well "model_output" translates the English answer into the target language.
Keep in mind: the answer is a concise factual response (a name, date, number, place, or yes/no). The translation must preserve the same factual content as the English answer, in the target language, while remaining natural.
Scoring rubric (decide internally; do not print sub-scores):
Faithfulness (70%): The translated answer conveys the same fact(s) as the English answer. For yes/no answers the polarity must match.
Terminology, Entities, Numbers (20%): Names, numbers, dates, and entities preserved and correct.
Fluency (10%): Natural, grammatical form in the target language for a short answer.
Critical error floors:
Wrong language or untranslated English copy -> <=10
Opposite yes/no polarity or completely different fact -> <=20
Hallucinated content not grounded in the English answer -> <=40
Loss/corruption of critical numbers, names, or dates -> <=60
Guidance: Names that are conventionally kept in Latin script in the target language should not be penalized. Minor transliteration differences are acceptable.
Round to the nearest integer and clamp to [0,100]. If inputs are empty or unusable, return 0.

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate answer translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100."""  # noqa: E501

_JUDGE_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "rationale", "error_tags"],
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "rationale": {"type": "string", "minLength": 1},
        "error_tags": {"type": "array", "items": {"type": "string"}},
    },
}

JUDGE_SYSTEM_PROMPT = (
    "You are a meticulous bilingual translation evaluator. Compare the English source "
    "with the candidate in the declared target language. Score semantic faithfulness "
    "(60%), entities/numbers/terminology (15%), fluency/grammar (20%), and register "
    "(5%). Wrong-language or substantially untranslated output must score at most 10; "
    "a contradiction or hallucinated key content at most 40; corrupted critical names "
    "or numbers at most 60. Return exactly one JSON object satisfying response_schema. "
    "Do not add Markdown or hidden reasoning. Keep rationale to at most three sentences."
)
JUDGE_ANSWER_SYSTEM_PROMPT = (
    "You are a meticulous bilingual evaluator of short factual answer translations. "
    "Use the English question only as context. Score factual faithfulness (70%), "
    "entities/numbers (20%), and fluency (10%). Opposite yes/no polarity or a different "
    "fact must score at most 20; wrong-language or substantially untranslated output at "
    "most 10. Return exactly one JSON object satisfying response_schema. Do not add "
    "Markdown or hidden reasoning. Keep rationale to at most three sentences."
)


def _prompt_hash(system_prompt: str, answer_prompt: str, schema: object) -> str:
    payload = canonical_json(
        {"system_prompt": system_prompt, "answer_prompt": answer_prompt, "schema": schema}
    )
    return hashlib.sha256(payload.encode()).hexdigest()


JUDGE_PROMPT_HASH = _prompt_hash(
    JUDGE_SYSTEM_PROMPT,
    JUDGE_ANSWER_SYSTEM_PROMPT,
    _JUDGE_RESPONSE_SCHEMA,
)
LEGACY_JUDGE_PROMPT_HASH = _prompt_hash(
    LEGACY_JUDGE_SYSTEM_PROMPT,
    LEGACY_JUDGE_ANSWER_SYSTEM_PROMPT,
    {"format": "explanation followed by SCORE: <integer>"},
)

_ENVIRONMENT_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET = re.compile(
    r"(?:hf_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})"
)


@dataclass(frozen=True, slots=True)
class JudgeConfig:
    """Credential-safe configuration for an OpenAI-compatible judge endpoint."""

    model_id: str
    backend: str = "openai_compatible"
    base_url_env: str = "OPENAI_BASE_URL"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: float = 600.0
    http_max_retries: int = 2
    response_max_attempts: int = 2
    max_workers: int = 1
    seed: int = 20260810
    temperature: float = 0.0
    max_new_tokens: int = 512
    paragraph_sample_per_language: int = 80
    question_sample_per_language: int = 20
    answer_sample_per_language: int = 20

    def __post_init__(self) -> None:
        if self.backend != "openai_compatible":
            raise ValueError("backend must be 'openai_compatible'")
        if not self.model_id.strip():
            raise ValueError("model_id must be non-empty")
        for env_name, env_value in (
            ("base_url_env", self.base_url_env),
            ("api_key_env", self.api_key_env),
        ):
            if not _ENVIRONMENT_VARIABLE.fullmatch(env_value):
                raise ValueError(f"{env_name} is not a valid environment-variable name")
        if self.base_url_env == self.api_key_env:
            raise ValueError("base_url_env and api_key_env must differ")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        for int_name, int_value, minimum in (
            ("http_max_retries", self.http_max_retries, 0),
            ("response_max_attempts", self.response_max_attempts, 1),
            ("max_workers", self.max_workers, 1),
            ("seed", self.seed, 0),
            ("max_new_tokens", self.max_new_tokens, 1),
            ("paragraph_sample_per_language", self.paragraph_sample_per_language, 0),
            ("question_sample_per_language", self.question_sample_per_language, 0),
            ("answer_sample_per_language", self.answer_sample_per_language, 0),
        ):
            if isinstance(int_value, bool) or not isinstance(int_value, int) or int_value < minimum:
                raise ValueError(f"{int_name} must be an integer >= {minimum}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")

    @classmethod
    def from_yaml(cls, path: Path) -> JudgeConfig:
        import yaml

        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
            raise ValueError(f"Expected a YAML mapping in {path}")
        try:
            return cls(**cast(dict[str, Any], loaded))
        except TypeError as error:
            raise ValueError(f"Invalid judge configuration in {path}: {error}") from error


@dataclass(frozen=True, slots=True)
class SourceParagraph:
    title: str
    sentences: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    split: str
    question: str
    answer: str
    context: tuple[SourceParagraph, ...]


def load_source_records(
    source_paths: Mapping[str, Path | None],
) -> dict[str, SourceRecord]:
    """Load and validate typed HotpotQA source records for every requested split."""
    records: dict[str, SourceRecord] = {}
    for split in sorted(source_paths):
        path = source_paths[split]
        if path is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON array in {path}")
        for position, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(f"Source row {position} in {path} is not an object")
            source_id = str(item.get("_id", item.get("id", "")))
            if not source_id:
                raise ValueError(f"Source row {position} in {path} lacks _id/id")
            if source_id in records:
                raise ValueError(f"Duplicate source_id across source files: {source_id!r}")
            raw_context = item.get("context")
            if not isinstance(raw_context, list):
                raise ValueError(f"Source {source_id!r} has invalid context")
            context: list[SourceParagraph] = []
            for paragraph in raw_context:
                if (
                    not isinstance(paragraph, list)
                    or len(paragraph) != 2
                    or not isinstance(paragraph[0], str)
                    or not isinstance(paragraph[1], list)
                    or not all(isinstance(sentence, str) for sentence in paragraph[1])
                ):
                    raise ValueError(f"Source {source_id!r} has a malformed paragraph")
                context.append(SourceParagraph(paragraph[0], tuple(paragraph[1])))
            records[source_id] = SourceRecord(
                source_id=source_id,
                split=split,
                question=str(item.get("question", "")),
                answer=str(item.get("answer", "")),
                context=tuple(context),
            )
    return records


@dataclass(frozen=True, slots=True)
class JudgeRecord:
    instance_id: str
    source_id: str
    source_split: str
    language: str
    unit: JudgeUnit
    source_text: str
    candidate_text: str
    paragraph_id: str | None = None
    context_question: str = ""

    @property
    def record_id(self) -> str:
        identity = canonical_json(
            {
                "instance_id": self.instance_id,
                "language": self.language,
                "paragraph_id": self.paragraph_id,
                "source_id": self.source_id,
                "unit": self.unit,
            }
        )
        return hashlib.sha256(identity.encode()).hexdigest()

    def user_prompt(self) -> str:
        language = LANGUAGE_BY_CODE.get(self.language)
        payload: dict[str, object] = {
            "unit": self.unit,
            "source_language": "English",
            "target_language_code": self.language,
            "target_language_name": language.name if language is not None else self.language,
            "source_text": self.source_text,
            "candidate_text": self.candidate_text,
            "response_schema": _JUDGE_RESPONSE_SCHEMA,
        }
        if self.context_question:
            payload["context_question"] = self.context_question
        return canonical_json(payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SAMPLE_SCHEMA_VERSION,
            "record_id": self.record_id,
            "instance_id": self.instance_id,
            "source_id": self.source_id,
            "source_split": self.source_split,
            "language": self.language,
            "unit": self.unit,
            "paragraph_id": self.paragraph_id,
            "source_text": self.source_text,
            "candidate_text": self.candidate_text,
            "context_question": self.context_question,
        }


@dataclass(frozen=True, slots=True)
class JudgeResult:
    record: JudgeRecord
    score: int | None
    rationale: str = ""
    error_tags: tuple[str, ...] = ()
    raw_response: str = ""
    error: str | None = None
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class LanguageSummary:
    language: str
    language_name: str
    paragraph_count: int
    question_count: int
    answer_count: int
    paragraph_score_mean: float | None
    question_score_mean: float | None
    answer_score_mean: float | None


@dataclass(frozen=True, slots=True)
class JudgeReport:
    schema_version: str
    model_id: str
    prompt_version: str
    prompt_hash: str
    sample_manifest_sha256: str
    seed: int
    total_units: int
    judged_units: int
    failed_units: int
    overall_score_mean: float | None
    by_language: tuple[LanguageSummary, ...] = ()
    by_unit: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    application_retry_count: int = 0


def sample_units(
    instances: Iterable[XHotpotInstance],
    source_records: Mapping[str, SourceRecord],
    *,
    paragraph_per_language: int = 80,
    question_per_language: int = 20,
    answer_per_language: int = 20,
    seed: int = 20260810,
) -> list[JudgeRecord]:
    """Build a deterministic, language-balanced manifest with paired QA sampling."""
    paragraph_buckets: dict[str, list[JudgeRecord]] = {}
    qa_buckets: dict[str, list[tuple[JudgeRecord, JudgeRecord]]] = {}
    for instance in instances:
        for candidate in instance.candidates:
            if candidate.language == "en":
                continue
            if candidate.source_sentences is None:
                raise ValueError(
                    f"Instance {instance.id!r} candidate {candidate.id!r} lacks source_sentences"
                )
            paragraph_buckets.setdefault(candidate.language, []).append(
                JudgeRecord(
                    instance_id=instance.id,
                    source_id=instance.source_id,
                    source_split=instance.source_split,
                    language=candidate.language,
                    unit=JUDGE_UNIT_PARAGRAPH,
                    paragraph_id=candidate.id,
                    source_text=" ".join(candidate.source_sentences),
                    candidate_text=" ".join(candidate.sentences),
                )
            )

        language = instance.question_language
        if language == "en":
            continue
        source = source_records.get(instance.source_id)
        if source is None:
            raise ValueError(f"Missing HotpotQA source record for {instance.source_id!r}")
        question = JudgeRecord(
            instance_id=instance.id,
            source_id=instance.source_id,
            source_split=instance.source_split,
            language=language,
            unit=JUDGE_UNIT_QUESTION,
            source_text=source.question,
            candidate_text=instance.question,
        )
        answer = JudgeRecord(
            instance_id=instance.id,
            source_id=instance.source_id,
            source_split=instance.source_split,
            language=language,
            unit=JUDGE_UNIT_ANSWER,
            source_text=source.answer,
            candidate_text=instance.answer,
            context_question=source.question,
        )
        qa_buckets.setdefault(language, []).append((question, answer))

    sampled: list[JudgeRecord] = []
    for language in sorted(set(paragraph_buckets) | set(qa_buckets)):
        paragraphs = _stable_sample(
            paragraph_buckets.get(language, []),
            paragraph_per_language,
            seed=seed,
            stratum=f"{language}:paragraph",
        )
        sampled.extend(paragraphs)
        qa_pairs = _stable_sample_pairs(
            qa_buckets.get(language, []),
            max(question_per_language, answer_per_language),
            seed=seed,
            stratum=f"{language}:qa",
        )
        sampled.extend(pair[0] for pair in qa_pairs[:question_per_language])
        sampled.extend(pair[1] for pair in qa_pairs[:answer_per_language])
    return sampled


def _stable_sample(
    records: Sequence[JudgeRecord],
    count: int,
    *,
    seed: int,
    stratum: str,
) -> list[JudgeRecord]:
    ranked = sorted(
        records,
        key=lambda record: (_rank(seed, stratum, record.record_id), record.record_id),
    )
    return ranked[:count]


def _stable_sample_pairs(
    records: Sequence[tuple[JudgeRecord, JudgeRecord]],
    count: int,
    *,
    seed: int,
    stratum: str,
) -> list[tuple[JudgeRecord, JudgeRecord]]:
    ranked = sorted(
        records,
        key=lambda pair: (_rank(seed, stratum, pair[0].instance_id), pair[0].record_id),
    )
    return ranked[:count]


def _rank(seed: int, stratum: str, identity: str) -> str:
    return hashlib.sha256(f"{seed}\0{stratum}\0{identity}".encode()).hexdigest()


class TranslationJudge:
    """Strict JSON judge with thread-local real clients and bounded retries."""

    def __init__(self, config: JudgeConfig, *, client: Any | None = None) -> None:
        self._config = config
        self._provided_client = client
        self._clients = threading.local()

    def _get_client(self) -> Any:
        if self._provided_client is not None:
            return self._provided_client
        client = getattr(self._clients, "client", None)
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    'Install evaluation dependencies with pip install -e ".[generation]"'
                ) from error
            base_url, api_key = _connection_settings(self._config)
            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=self._config.timeout_seconds,
                max_retries=self._config.http_max_retries,
            )
            self._clients.client = client
        return client

    def judge(self, record: JudgeRecord) -> JudgeResult:
        prompt = (
            JUDGE_ANSWER_SYSTEM_PROMPT if record.unit == JUDGE_UNIT_ANSWER else JUDGE_SYSTEM_PROMPT
        )
        last_error: str | None = None
        last_raw = ""
        for attempt in range(1, self._config.response_max_attempts + 1):
            try:
                response = self._get_client().chat.completions.create(
                    model=self._config.model_id,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": record.user_prompt()},
                    ],
                    max_tokens=self._config.max_new_tokens,
                    temperature=self._config.temperature,
                    seed=self._config.seed,
                    response_format={"type": "json_object"},
                )
                content = getattr(response.choices[0].message, "content", None)
                if not isinstance(content, str):
                    raise ValueError("Judge returned no string content")
                last_raw = content.strip()
                score, rationale, tags = _parse_judge_response(last_raw)
                return JudgeResult(
                    record=record,
                    score=score,
                    rationale=rationale,
                    error_tags=tags,
                    raw_response=last_raw,
                    attempts=attempt,
                )
            except Exception as error:  # noqa: BLE001 - persisted without credentials
                last_error = _safe_error(error)
                if attempt < self._config.response_max_attempts:
                    time.sleep(min(float(attempt), 3.0))
        return JudgeResult(
            record=record,
            score=None,
            raw_response=_SECRET.sub("<redacted>", last_raw)[:10_000],
            error=last_error,
            attempts=self._config.response_max_attempts,
        )


def _parse_judge_response(text: str) -> tuple[int, str, tuple[str, ...]]:
    parsed = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    if not isinstance(parsed, dict) or set(parsed) != {"score", "rationale", "error_tags"}:
        raise ValueError("Judge response must contain only score, rationale, and error_tags")
    score = parsed["score"]
    rationale = parsed["rationale"]
    tags = parsed["error_tags"]
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("Judge score must be an integer in [0, 100]")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("Judge rationale must be a non-empty string")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("Judge error_tags must be an array of strings")
    return score, rationale.strip(), tuple(tag.strip() for tag in tags if tag.strip())


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def run_judge(
    instances: Iterable[XHotpotInstance],
    config: JudgeConfig,
    *,
    source_records: Mapping[str, SourceRecord],
    output_path: Path,
    progress: bool = True,
    judge: TranslationJudge | None = None,
) -> JudgeReport:
    """Create/replay a sample manifest, resume results, compact, and report."""
    records = sample_units(
        instances,
        source_records,
        paragraph_per_language=config.paragraph_sample_per_language,
        question_per_language=config.question_sample_per_language,
        answer_per_language=config.answer_sample_per_language,
        seed=config.seed,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path = _artifact_path(output_path, ".sample.jsonl")
    records_path = _artifact_path(output_path, ".records.jsonl")
    report_path = _artifact_path(output_path, ".report.json")

    with _exclusive_prefix_lock(output_path):
        sample_bytes = _ensure_sample_manifest(sample_path, records)
        sample_hash = hashlib.sha256(sample_bytes).hexdigest()
        results = _load_results(records_path, records, config, sample_hash)
        pending = [record for record in records if results.get(record.record_id, None) is None]
        pending.extend(
            record
            for record in records
            if record.record_id in results and results[record.record_id].score is None
        )
        evaluator = judge or TranslationJudge(config)
        progress_bar = _progress_bar(len(pending), progress)
        try:
            with records_path.open("a", encoding="utf-8", newline="\n") as stream:
                for result in _judge_concurrently(evaluator, pending, config.max_workers):
                    results[result.record.record_id] = result
                    stream.write(
                        canonical_json(_result_to_dict(result, config, sample_hash)) + "\n"
                    )
                    stream.flush()
                    if progress_bar is not None:
                        progress_bar.update(1)
                os.fsync(stream.fileno())
        finally:
            if progress_bar is not None:
                progress_bar.close()

        ordered_results = [results[record.record_id] for record in records]
        _compact_results(records_path, ordered_results, config, sample_hash)
        report = build_report(
            ordered_results,
            config=config,
            sample_manifest_sha256=sample_hash,
        )
        _atomic_write(
            report_path,
            (json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n").encode(),
        )
    return report


def _judge_concurrently(
    judge: TranslationJudge,
    records: Sequence[JudgeRecord],
    max_workers: int,
) -> Iterator[JudgeResult]:
    if max_workers == 1:
        for record in records:
            yield judge.judge(record)
        return
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[Future[JudgeResult], JudgeRecord] = {
            executor.submit(judge.judge, record): record for record in records
        }
        for future in as_completed(futures):
            record = futures[future]
            try:
                yield future.result()
            except Exception as error:  # noqa: BLE001 - defensive worker isolation
                yield JudgeResult(record=record, score=None, error=_safe_error(error))


def build_report(
    results: Sequence[JudgeResult],
    *,
    config: JudgeConfig,
    sample_manifest_sha256: str,
) -> JudgeReport:
    by_language: dict[str, list[JudgeResult]] = {}
    by_unit: dict[str, list[JudgeResult]] = {}
    for result in results:
        by_language.setdefault(result.record.language, []).append(result)
        by_unit.setdefault(result.record.unit, []).append(result)

    summaries: list[LanguageSummary] = []
    for language in sorted(by_language):
        values = by_language[language]
        paragraph = [item for item in values if item.record.unit == JUDGE_UNIT_PARAGRAPH]
        question = [item for item in values if item.record.unit == JUDGE_UNIT_QUESTION]
        answer = [item for item in values if item.record.unit == JUDGE_UNIT_ANSWER]
        definition = LANGUAGE_BY_CODE.get(language)
        summaries.append(
            LanguageSummary(
                language=language,
                language_name=definition.name if definition is not None else language,
                paragraph_count=len(paragraph),
                question_count=len(question),
                answer_count=len(answer),
                paragraph_score_mean=_mean(paragraph),
                question_score_mean=_mean(question),
                answer_score_mean=_mean(answer),
            )
        )

    unit_report: dict[str, dict[str, float | int | None]] = {}
    for unit, values in sorted(by_unit.items()):
        scores = [result.score for result in values if result.score is not None]
        unit_report[unit] = {
            "count": len(values),
            "judged": len(scores),
            "failed": len(values) - len(scores),
            "score_mean": sum(scores) / len(scores) if scores else None,
            "score_min": min(scores) if scores else None,
            "score_max": max(scores) if scores else None,
        }
    scores = [result.score for result in results if result.score is not None]
    return JudgeReport(
        schema_version=REPORT_SCHEMA_VERSION,
        model_id=config.model_id,
        prompt_version=JUDGE_PROMPT_VERSION,
        prompt_hash=JUDGE_PROMPT_HASH,
        sample_manifest_sha256=sample_manifest_sha256,
        seed=config.seed,
        total_units=len(results),
        judged_units=len(scores),
        failed_units=len(results) - len(scores),
        overall_score_mean=sum(scores) / len(scores) if scores else None,
        by_language=tuple(summaries),
        by_unit=unit_report,
        application_retry_count=sum(max(result.attempts - 1, 0) for result in results),
    )


def _mean(results: Sequence[JudgeResult]) -> float | None:
    scores = [result.score for result in results if result.score is not None]
    return sum(scores) / len(scores) if scores else None


def _ensure_sample_manifest(path: Path, records: Sequence[JudgeRecord]) -> bytes:
    payload = b"".join((canonical_json(record.to_dict()) + "\n").encode() for record in records)
    if path.exists():
        existing = path.read_bytes()
        if existing != payload:
            raise ValueError(
                f"Sample manifest {path} does not match the deterministic sample; "
                "use a new output prefix for a different dataset or sampling configuration"
            )
        return existing
    _atomic_write(path, payload)
    return payload


def _load_results(
    path: Path,
    records: Sequence[JudgeRecord],
    config: JudgeConfig,
    sample_hash: str,
) -> dict[str, JudgeResult]:
    expected = {record.record_id: record for record in records}
    results: dict[str, JudgeResult] = {}
    if not path.exists():
        return results
    for item in read_jsonl(path):
        record_id = item.get("record_id")
        if not isinstance(record_id, str) or record_id not in expected:
            raise ValueError(f"Result file {path} contains an unknown or legacy record_id")
        if (
            item.get("model_id") != config.model_id
            or item.get("prompt_hash") != JUDGE_PROMPT_HASH
            or item.get("sample_manifest_sha256") != sample_hash
        ):
            raise ValueError(f"Result file {path} has incompatible judge provenance")
        score = item.get("score")
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100
        ):
            raise ValueError(f"Result file {path} contains an invalid score")
        raw_tags = item.get("error_tags", [])
        if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
            raise ValueError(f"Result file {path} contains invalid error_tags")
        results[record_id] = JudgeResult(
            record=expected[record_id],
            score=score,
            rationale=str(item.get("rationale", "")),
            error_tags=tuple(raw_tags),
            raw_response=str(item.get("raw_response", "")),
            error=str(item["error"]) if item.get("error") is not None else None,
            attempts=int(item.get("attempts", 1)),
        )
    return results


def _result_to_dict(
    result: JudgeResult,
    config: JudgeConfig,
    sample_hash: str,
) -> dict[str, object]:
    return {
        **result.record.to_dict(),
        "schema_version": RESULT_SCHEMA_VERSION,
        "model_id": config.model_id,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "prompt_hash": JUDGE_PROMPT_HASH,
        "sample_manifest_sha256": sample_hash,
        "score": result.score,
        "rationale": result.rationale,
        "error_tags": list(result.error_tags),
        "raw_response": result.raw_response,
        "error": result.error,
        "attempts": result.attempts,
    }


def _compact_results(
    path: Path,
    results: Sequence[JudgeResult],
    config: JudgeConfig,
    sample_hash: str,
) -> None:
    payload = b"".join(
        (canonical_json(_result_to_dict(result, config, sample_hash)) + "\n").encode()
        for result in results
    )
    _atomic_write(path, payload)


def _connection_settings(config: JudgeConfig) -> tuple[str, str]:
    base_url = os.environ.get(config.base_url_env, "").strip()
    if not base_url:
        raise RuntimeError(f"Set {config.base_url_env} to the OpenAI-compatible base URL")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"{config.base_url_env} must be an http(s) URL without credentials or query data"
        )
    api_key = os.environ.get(config.api_key_env, "").strip()
    if not api_key:
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError(f"Set {config.api_key_env} for a non-loopback endpoint")
        api_key = "EMPTY"
    return base_url.rstrip("/"), api_key


def _safe_error(error: Exception) -> str:
    message = _SECRET.sub("<redacted>", str(error)).replace("\r", " ").replace("\n", " ")
    return f"{type(error).__name__}: {message[:500]}"


def _artifact_path(prefix: Path, ending: str) -> Path:
    return prefix.with_name(prefix.name + ending)


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_prefix_lock(prefix: Path) -> Iterator[None]:
    path = _artifact_path(prefix, ".lock")
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(f"Judge output prefix is already locked: {prefix}") from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def _progress_bar(total: int, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        from tqdm.auto import tqdm  # type: ignore[import-untyped]
    except ImportError:
        return None
    return tqdm(total=total, desc="judge", unit="unit", dynamic_ncols=True)

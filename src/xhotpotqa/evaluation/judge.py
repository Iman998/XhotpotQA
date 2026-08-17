"""LLM-as-a-judge quality evaluation for XHotpotQA v2 translations.

Evaluates translation quality of candidate paragraphs and questions across all
target languages using a reference-based and a reference-free rubric, producing
per-language, per-record, and aggregate reports.

Each translation unit receives two integer scores in [0, 100]:
  * ``score_reference``    - judged against the English source (ground truth)
  * ``score_no_reference`` - judged from the source alone (no gold translation)

The judge model is queried through an OpenAI-compatible chat endpoint with
thread-safe retry/backoff so the evaluation can be parallelised.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.languages import LANGUAGE_BY_CODE

_SCORE_PATTERN = re.compile(r"SCORE\s*[:\-]?\s*(\d{1,3})", re.IGNORECASE)
_INTEGER_PATTERN = re.compile(r"\b(\d{1,3})\b")

JUDGE_UNIT_PARAGRAPH = "paragraph"
JUDGE_UNIT_QUESTION = "question"
JUDGE_UNIT_ANSWER = "answer"

_PARAGRAPH_SAMPLE_PER_LANG = 80
_QUESTION_SAMPLE_PER_LANG = 20

_SYSTEM_PROMPT = """You are a meticulous bilingual translation judge. Your task is to assign a single integer score from 0 to 100 (0 = unusable, 100 = excellent) for a candidate translation, using only the source text and the target candidate.
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

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100."""

_SYSTEM_PROMPT_ANSWER = """You are a meticulous bilingual translation judge for short answers. You are given an English question ("context_question") and its short English answer ("text") alongside a translated answer ("model_output"). Your task is to judge how well "model_output" translates the English answer into the target language.
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

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate answer translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100."""


@dataclass(frozen=True, slots=True)
class JudgeConfig:
    """Configuration for the LLM-as-judge evaluation."""

    base_url: str
    api_key: str
    model_name: str
    timeout_seconds: float = 6000.0
    max_retries: int = 2
    max_workers: int = 1
    seed: int = 20260810
    max_tokens: int = 4000
    paragraph_sample_per_lang: int = _PARAGRAPH_SAMPLE_PER_LANG
    question_sample_per_lang: int = _QUESTION_SAMPLE_PER_LANG
    source_train: str | None = None
    source_validation: str | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> JudgeConfig:
        import yaml

        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not all(isinstance(k, str) for k in loaded):
            raise ValueError(f"Expected a YAML mapping in {path}")
        raw = cast_mapping(loaded)
        api = raw.get("api", {})
        if not isinstance(api, dict):
            raise ValueError("api section must be a mapping")
        api = cast_mapping(api)
        qg = raw.get("question_generation", {})
        if not isinstance(qg, dict):
            raise ValueError("question_generation section must be a mapping")
        qg = cast_mapping(qg)
        judge = raw.get("judge", {})
        if not isinstance(judge, dict):
            raise ValueError("judge section must be a mapping")
        judge = cast_mapping(judge)
        source = raw.get("source", {})
        if not isinstance(source, dict):
            raise ValueError("source section must be a mapping")
        source = cast_mapping(source)
        return cls(
            base_url=api.get("base_url", ""),
            api_key=api.get("api_key", ""),
            model_name=qg.get("model_name", ""),
            timeout_seconds=float(api.get("timeout_seconds", 6000)),
            max_retries=int(api.get("max_retries", 2)),
            max_workers=int(judge.get("max_workers", 1)),
            seed=int(judge.get("seed", 20260810)),
            max_tokens=int(api.get("max_new_tokens", judge.get("max_tokens", 4000))),
            paragraph_sample_per_lang=int(
                judge.get("paragraph_sample_per_lang", _PARAGRAPH_SAMPLE_PER_LANG)
            ),
            question_sample_per_lang=int(
                judge.get("question_sample_per_lang", _QUESTION_SAMPLE_PER_LANG)
            ),
            source_train=source.get("train"),
            source_validation=source.get("validation"),
        )


def cast_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


@dataclass(slots=True)
class JudgeRecord:
    """A single translation unit to be judged."""

    instance_id: str
    source_id: str
    source_split: str
    language: str
    unit: str
    source_text: str
    candidate_text: str
    ground_truth: str
    paragraph_id: str | None = None
    context_question: str = ""

    def user_prompt(self) -> str:
        payload: dict[str, object] = {
            "source_language": "en",
            "target_language": self.language,
            "text": self.source_text,
            "model_output": self.candidate_text,
        }
        if self.context_question:
            payload["context_question"] = self.context_question
        return json.dumps(payload, ensure_ascii=False)


@dataclass(slots=True)
class JudgeResult:
    """The outcome of judging a single :class:`JudgeRecord`."""

    record: JudgeRecord
    score: int | None
    judge_text: str = ""
    reasoning: str = ""
    error: str | None = None


@dataclass(slots=True)
class LanguageSummary:
    language: str
    language_name: str
    paragraph_count: int
    question_count: int
    answer_count: int
    paragraph_score_mean: float | None
    paragraph_score_min: int | None
    paragraph_score_max: int | None
    question_score_mean: float | None
    question_score_min: int | None
    question_score_max: int | None
    answer_score_mean: float | None


@dataclass(slots=True)
class JudgeReport:
    model_name: str
    total_units: int
    judged_units: int
    failed_units: int
    overall_score_mean: float | None
    by_language: list[LanguageSummary] = field(default_factory=list)
    by_unit: dict[str, dict[str, float | None]] = field(default_factory=dict)
    retry_count: int = 0


def _extract_score(text: str) -> int | None:
    """Parse an integer score in [0, 100] from the judge output.

    Prefers an explicit ``SCORE: <n>`` marker; falls back to the last integer
    token in the text, clamped to the valid range.
    """
    if not text:
        return None
    match = _SCORE_PATTERN.search(text)
    candidates: list[int] = []
    if match:
        candidates.append(int(match.group(1)))
    else:
        candidates.extend(int(m) for m in _INTEGER_PATTERN.findall(text))
    if not candidates:
        return None
    score = max(0, min(100, candidates[-1]))
    return score


class TranslationJudge:
    """Thread-safe LLM-as-judge that scores translation units in parallel."""

    def __init__(self, config: JudgeConfig, *, client: Any | None = None) -> None:
        self._config = config
        self._client = client
        self._client_lock = threading.Lock()
        self._retry_lock = threading.Lock()
        self._retry_count = 0

    @property
    def retry_count(self) -> int:
        with self._retry_lock:
            return self._retry_count

    def _get_client(self) -> Any:
        with self._client_lock:
            if self._client is None:
                try:
                    from openai import OpenAI
                except ImportError as error:
                    raise RuntimeError(
                        'Install generation dependencies with pip install -e ".[generation]"'
                    ) from error
                self._client = OpenAI(
                    base_url=self._config.base_url,
                    api_key=self._config.api_key,
                    timeout=self._config.timeout_seconds,
                    max_retries=0,
                )
            return self._client

    def _score_once(
        self, system_prompt: str, user_prompt: str
    ) -> tuple[int | None, str, str]:
        """Return ``(score, judge_text, reasoning)`` for one judge call.

        ``judge_text`` is the visible assistant content (explanation + score);
        ``reasoning`` is the model's hidden reasoning trace when the endpoint
        exposes it (e.g. glm-5.2 thinking mode), otherwise an empty string.
        """
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._config.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._config.max_tokens,
            temperature=0.0,
            seed=self._config.seed,
        )
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        text = content.strip()
        reasoning = getattr(message, "reasoning", None)
        if not isinstance(reasoning, str):
            reasoning = getattr(message, "reasoning_content", None)
        if not isinstance(reasoning, str):
            reasoning = ""
        reasoning = reasoning.strip()
        score = _extract_score(text)
        if score is None and reasoning:
            score = _extract_score(reasoning)
        return score, text, reasoning

    def _score_safe(
        self, system_prompt: str, user_prompt: str, *, retries: int | None = None
    ) -> tuple[int | None, str, str, str | None]:
        """Return ``(score, judge_text, reasoning, error)`` with retry/backoff."""
        attempts = retries if retries is not None else self._config.max_retries
        last_error: str | None = None
        last_text = ""
        last_reasoning = ""
        for attempt in range(1, attempts + 1):
            try:
                score, text, reasoning = self._score_once(system_prompt, user_prompt)
                last_text, last_reasoning = text, reasoning
                if score is not None:
                    return score, text, reasoning, None
                last_error = "model did not return a parseable integer"
            except Exception as error:  # noqa: BLE001
                last_error = str(error)
                with self._retry_lock:
                    self._retry_count += 1
            if attempt < attempts:
                time.sleep(min(2.0 * attempt, 10.0))
        return None, last_text, last_reasoning, last_error

    def judge(self, record: JudgeRecord) -> JudgeResult:
        prompt = _SYSTEM_PROMPT_ANSWER if record.unit == JUDGE_UNIT_ANSWER else _SYSTEM_PROMPT
        score, text, reasoning, error = self._score_safe(prompt, record.user_prompt())
        return JudgeResult(
            record=record,
            score=score,
            judge_text=text,
            reasoning=reasoning,
            error=error,
        )

    def judge_batch(
        self,
        records: Sequence[JudgeRecord],
        *,
        progress: bool = True,
    ) -> list[JudgeResult]:
        results: list[JudgeResult] = []
        if not records:
            return results
        workers = max(1, self._config.max_workers)
        progress_bar = None
        if progress:
            try:
                from tqdm.auto import tqdm

                progress_bar = tqdm(
                    total=len(records), desc="judge", unit="unit", dynamic_ncols=True
                )
            except ImportError:
                progress_bar = None
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.judge, record): idx for idx, record in enumerate(records)}
            ordered: dict[int, JudgeResult] = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    ordered[idx] = future.result()
                except Exception as error:  # noqa: BLE001
                    ordered[idx] = JudgeResult(
                        record=records[idx],
                        score_reference=None,
                        score_no_reference=None,
                        judge_text_reference="",
                        judge_text_no_reference="",
                        error=str(error),
                    )
                if progress_bar is not None:
                    progress_bar.update(1)
        if progress_bar is not None:
            progress_bar.close()
        results = [ordered[i] for i in range(len(records))]
        return results


def load_source_records(
    source_paths: Mapping[str, Path | None]
) -> dict[str, dict[str, str]]:
    """Map ``source_id -> {"question": ..., "answer": ...}`` from HotpotQA."""
    mapping: dict[str, dict[str, str]] = {}
    for split, path in source_paths.items():
        if path is None or not Path(path).exists():
            continue
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON array in {path}")
        for item in payload:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("_id", item.get("id", "")))
            if sid and sid not in mapping:
                mapping[sid] = {
                    "question": str(item.get("question", "")),
                    "answer": str(item.get("answer", "")),
                }
    return mapping


def load_source_questions(
    source_paths: Mapping[str, Path | None]
) -> dict[str, str]:
    """Backward-compatible: return ``source_id -> English question``."""
    return {sid: rec["question"] for sid, rec in load_source_records(source_paths).items()}


def sample_units(
    instances: Iterable[XHotpotInstance],
    source_questions: Mapping[str, str] | Mapping[str, Mapping[str, str]],
    *,
    paragraph_per_lang: int = _PARAGRAPH_SAMPLE_PER_LANG,
    question_per_lang: int = _QUESTION_SAMPLE_PER_LANG,
    seed: int = 20260810,
) -> list[JudgeRecord]:
    """Sample a deterministic, language-balanced set of translation units.

    For every language present in the dataset, sample up to
    ``paragraph_per_lang`` candidate paragraphs and up to
    ``question_per_lang`` questions/answers. Paragraph source text is the joined
    English source sentences; the candidate text is the joined translated
    sentences. Question source text is the original HotpotQA English question.
    Answer source text is the original English answer, with the English question
    attached as ``context_question`` so the judge understands the answer is a
    response to that question.
    """
    import random

    def _get_source(rec: object, key: str) -> str:
        if isinstance(rec, str):
            return rec if key == "question" else ""
        if isinstance(rec, Mapping):
            return str(rec.get(key, ""))
        return ""

    rng = random.Random(seed)
    para_buckets: dict[str, list[JudgeRecord]] = {}
    question_buckets: dict[str, list[JudgeRecord]] = {}
    answer_buckets: dict[str, list[JudgeRecord]] = {}

    for instance in instances:
        for candidate in instance.candidates:
            lang = candidate.language
            if lang == "en" or not candidate.source_sentences:
                continue
            record = JudgeRecord(
                instance_id=instance.id,
                source_id=instance.source_id,
                source_split=instance.source_split,
                language=lang,
                unit=JUDGE_UNIT_PARAGRAPH,
                source_text=" ".join(candidate.source_sentences),
                candidate_text=" ".join(candidate.sentences),
                ground_truth=" ".join(candidate.source_sentences),
                paragraph_id=candidate.id,
            )
            para_buckets.setdefault(lang, []).append(record)

        q_lang = instance.question_language
        if q_lang and q_lang != "en":
            src_rec = source_questions.get(instance.source_id, "")
            source_question = _get_source(src_rec, "question")
            source_answer = _get_source(src_rec, "answer")
            q_record = JudgeRecord(
                instance_id=instance.id,
                source_id=instance.source_id,
                source_split=instance.source_split,
                language=q_lang,
                unit=JUDGE_UNIT_QUESTION,
                source_text=source_question,
                candidate_text=instance.question,
                ground_truth=source_question,
            )
            question_buckets.setdefault(q_lang, []).append(q_record)

            a_record = JudgeRecord(
                instance_id=instance.id,
                source_id=instance.source_id,
                source_split=instance.source_split,
                language=q_lang,
                unit=JUDGE_UNIT_ANSWER,
                source_text=source_answer,
                candidate_text=instance.answer,
                ground_truth="",
                context_question=source_question,
            )
            answer_buckets.setdefault(q_lang, []).append(a_record)

    sampled: list[JudgeRecord] = []
    all_languages = sorted(
        set(para_buckets) | set(question_buckets) | set(answer_buckets)
    )
    for lang in all_languages:
        paras = para_buckets.get(lang, [])
        if len(paras) <= paragraph_per_lang:
            sampled.extend(paras)
        else:
            sampled.extend(rng.sample(paras, paragraph_per_lang))
        questions = question_buckets.get(lang, [])
        if len(questions) <= question_per_lang:
            sampled.extend(questions)
        else:
            sampled.extend(rng.sample(questions, question_per_lang))
        answers = answer_buckets.get(lang, [])
        if len(answers) <= question_per_lang:
            sampled.extend(answers)
        else:
            sampled.extend(rng.sample(answers, question_per_lang))
    return sampled


def _mean(values: Sequence[int | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _extreme(values: Sequence[int | None], *, maximum: bool) -> int | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return max(nums) if maximum else min(nums)


def build_report(
    results: Sequence[JudgeResult],
    *,
    model_name: str,
) -> JudgeReport:
    by_lang: dict[str, list[JudgeResult]] = {}
    by_unit: dict[str, list[JudgeResult]] = {}
    for result in results:
        lang = result.record.language
        by_lang.setdefault(lang, []).append(result)
        by_unit.setdefault(result.record.unit, []).append(result)

    language_summaries: list[LanguageSummary] = []
    for lang in sorted(by_lang):
        lang_results = by_lang[lang]
        paras = [r for r in lang_results if r.record.unit == JUDGE_UNIT_PARAGRAPH]
        questions = [r for r in lang_results if r.record.unit == JUDGE_UNIT_QUESTION]
        answers = [r for r in lang_results if r.record.unit == JUDGE_UNIT_ANSWER]
        language_summaries.append(
            LanguageSummary(
                language=lang,
                language_name=LANGUAGE_BY_CODE.get(lang, type("L", (), {"name": lang})()).name,
                paragraph_count=len(paras),
                question_count=len(questions),
                answer_count=len(answers),
                paragraph_score_mean=_mean([r.score for r in paras]),
                paragraph_score_min=_extreme([r.score for r in paras], maximum=False),
                paragraph_score_max=_extreme([r.score for r in paras], maximum=True),
                question_score_mean=_mean([r.score for r in questions]),
                question_score_min=_extreme([r.score for r in questions], maximum=False),
                question_score_max=_extreme([r.score for r in questions], maximum=True),
                answer_score_mean=_mean([r.score for r in answers]),
            )
        )

    unit_stats: dict[str, dict[str, float | None]] = {}
    for unit, unit_results in by_unit.items():
        unit_stats[unit] = {
            "count": len(unit_results),
            "score_mean": _mean([r.score for r in unit_results]),
        }

    all_scores = [r.score for r in results]
    failed = sum(1 for r in results if r.score is None)
    return JudgeReport(
        model_name=model_name,
        total_units=len(results),
        judged_units=len(results) - failed,
        failed_units=failed,
        overall_score_mean=_mean(all_scores),
        by_language=language_summaries,
        by_unit=unit_stats,
    )


def run_judge(
    instances: Iterable[XHotpotInstance],
    config: JudgeConfig,
    *,
    source_questions: Mapping[str, str] | None = None,
    output_path: Path,
    progress: bool = True,
) -> JudgeReport:
    """Sample, judge, persist detailed results, and return an aggregate report.

    Results are streamed to disk: each judged unit is appended to
    ``<output>.records.jsonl`` as soon as it completes, so partial progress
    survives interruptions. A final ``<output>.report.json`` aggregate summary
    is written when all units have been judged.
    """
    source_questions = source_questions or {}
    records = sample_units(
        list(instances),
        source_questions,
        paragraph_per_lang=config.paragraph_sample_per_lang,
        question_per_lang=config.question_sample_per_lang,
        seed=config.seed,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records_path = output_path.with_suffix(output_path.suffix + ".records.jsonl")

    judge = TranslationJudge(config)
    write_lock = threading.Lock()
    progress_bar = None
    if progress:
        try:
            from tqdm.auto import tqdm

            progress_bar = tqdm(
                total=len(records), desc="judge", unit="unit", dynamic_ncols=True
            )
        except ImportError:
            progress_bar = None

    results: list[JudgeResult] = [None] * len(records)  # type: ignore[list-item]
    workers = max(1, config.max_workers)
    with records_path.open("w", encoding="utf-8", newline="\n") as stream:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(judge.judge, record): idx
                for idx, record in enumerate(records)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                except Exception as error:  # noqa: BLE001
                    result = JudgeResult(
                        record=records[idx],
                        score=None,
                        error=str(error),
                    )
                results[idx] = result
                rec = result.record
                with write_lock:
                    stream.write(
                        canonical_json(
                            {
                                "instance_id": rec.instance_id,
                                "source_id": rec.source_id,
                                "source_split": rec.source_split,
                                "language": rec.language,
                                "unit": rec.unit,
                                "paragraph_id": rec.paragraph_id,
                                "source_text": rec.source_text,
                                "candidate_text": rec.candidate_text,
                                "ground_truth": rec.ground_truth,
                                "score": result.score,
                                "judge_text": result.judge_text,
                                "reasoning": result.reasoning,
                                "error": result.error,
                            }
                        )
                        + "\n"
                    )
                    stream.flush()
                if progress_bar is not None:
                    progress_bar.update(1)

    if progress_bar is not None:
        progress_bar.close()

    report = build_report(results, model_name=config.model_name)
    report.retry_count = judge.retry_count
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")
    report_path.write_text(
        json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def _report_to_dict(report: JudgeReport) -> dict[str, Any]:
    payload = asdict(report)
    return payload

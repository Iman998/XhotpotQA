#!/usr/bin/env python3
"""Run the LLM-as-judge on XHotpotQA v1 (audited parquet) translations.

Loads v1 parquet files, samples 80 paragraphs + 20 questions + 20 answers per
language (combined train+validation), and judges each unit with a single score.
For paragraphs, the English candidate paragraph in the same record is used as
the source text. For questions/answers, the source_question/source_answer fields
are used directly.
"""
import json
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pyarrow.parquet as pq

from xhotpotqa.data.io import canonical_json
from xhotpotqa.evaluation.judge import (
    JudgeConfig,
    JudgeRecord,
    JudgeResult,
    JUDGE_UNIT_ANSWER,
    JUDGE_UNIT_PARAGRAPH,
    JUDGE_UNIT_QUESTION,
    TranslationJudge,
    build_report,
)
from xhotpotqa.languages import LANGUAGE_BY_CODE

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "configs" / "evaluation" / "judge_glm52.yaml"
V1_DIR = Path("/data/Iman/dataset/hf_sft/xhotpot/v1_audited")
OUTPUT_DIR = BASE / "data" / "processed"

# Map language name -> code for normalization
_LANG_NAME_TO_CODE = {lang.name: code for code, lang in LANGUAGE_BY_CODE.items()}


def _lang_code(name: str) -> str:
    if name in LANGUAGE_BY_CODE:
        return name
    return _LANG_NAME_TO_CODE.get(name, name)


def load_v1_records() -> list[dict]:
    records = []
    for pf in sorted(V1_DIR.glob("*.parquet")):
        table = pq.read_table(pf)
        records.extend(table.to_pylist())
        print(f"  {pf.name}: {table.num_rows} rows", flush=True)
    return records


def sample_v1_units(
    records: list[dict],
    *,
    paragraph_per_lang: int = 80,
    question_per_lang: int = 20,
    seed: int = 20260810,
) -> list[JudgeRecord]:
    import random

    rng = random.Random(seed)
    para_buckets: dict[str, list[JudgeRecord]] = {}
    question_buckets: dict[str, list[JudgeRecord]] = {}
    answer_buckets: dict[str, list[JudgeRecord]] = {}

    for rec in records:
        cands = rec.get("candidates", [])
        # Build English source paragraph by source_title
        english_paras: dict[str, str] = {}
        for c in cands:
            if (c.get("language_code") or _lang_code(c.get("language", ""))) == "en":
                key = c.get("source_title") or c.get("title", "")
                english_paras[key] = " ".join(c.get("sentences", []))

        for c in cands:
            lang = c.get("language_code") or _lang_code(c.get("language", ""))
            if lang == "en":
                continue
            sentences = c.get("sentences", [])
            if not sentences:
                continue
            key = c.get("source_title") or c.get("title", "")
            source_text = english_paras.get(key, "")
            if not source_text:
                continue
            record = JudgeRecord(
                instance_id=rec.get("id", ""),
                source_id=rec.get("source_id", ""),
                source_split=rec.get("source_split", ""),
                language=lang,
                unit=JUDGE_UNIT_PARAGRAPH,
                source_text=source_text,
                candidate_text=" ".join(sentences),
                ground_truth="",
                paragraph_id=c.get("paragraph_id", ""),
            )
            para_buckets.setdefault(lang, []).append(record)

        q_lang = _lang_code(rec.get("question_language", ""))
        if q_lang and q_lang != "en":
            source_question = rec.get("source_question", "")
            source_answer = rec.get("source_answer", "")
            q_record = JudgeRecord(
                instance_id=rec.get("id", ""),
                source_id=rec.get("source_id", ""),
                source_split=rec.get("source_split", ""),
                language=q_lang,
                unit=JUDGE_UNIT_QUESTION,
                source_text=source_question,
                candidate_text=rec.get("question", ""),
                ground_truth=source_question,
            )
            question_buckets.setdefault(q_lang, []).append(q_record)

            a_record = JudgeRecord(
                instance_id=rec.get("id", ""),
                source_id=rec.get("source_id", ""),
                source_split=rec.get("source_split", ""),
                language=q_lang,
                unit=JUDGE_UNIT_ANSWER,
                source_text=source_answer,
                candidate_text=rec.get("answer", ""),
                ground_truth="",
                context_question=source_question,
            )
            answer_buckets.setdefault(q_lang, []).append(a_record)

    sampled: list[JudgeRecord] = []
    all_langs = sorted(set(para_buckets) | set(question_buckets) | set(answer_buckets))
    for lang in all_langs:
        paras = para_buckets.get(lang, [])
        sampled.extend(paras if len(paras) <= paragraph_per_lang else rng.sample(paras, paragraph_per_lang))
        questions = question_buckets.get(lang, [])
        sampled.extend(questions if len(questions) <= question_per_lang else rng.sample(questions, question_per_lang))
        answers = answer_buckets.get(lang, [])
        sampled.extend(answers if len(answers) <= question_per_lang else rng.sample(answers, question_per_lang))
    return sampled


def main() -> None:
    config = JudgeConfig.from_yaml(CONFIG)
    print("Loading v1 parquet files...", flush=True)
    records = load_v1_records()
    print(f"Total v1 records: {len(records)}", flush=True)

    units = sample_v1_units(
        records,
        paragraph_per_lang=config.paragraph_sample_per_lang,
        question_per_lang=config.question_sample_per_lang,
        seed=config.seed,
    )
    from collections import Counter
    print(f"Sampled units: {len(units)}", flush=True)
    print(f"By unit: {dict(Counter(u.unit for u in units))}", flush=True)
    print(f"Languages: {len(set(u.language for u in units))}", flush=True)

    output_path = OUTPUT_DIR / "judge_v1"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_path = output_path.with_suffix(output_path.suffix + ".records.jsonl")

    # Resume support
    done: set[tuple[str, str, str]] = set()
    if records_path.exists():
        with records_path.open() as f:
            for line in f:
                r = json.loads(line)
                done.add((r["instance_id"], r["unit"], r.get("paragraph_id") or ""))
    remaining = [u for u in units if (u.instance_id, u.unit, u.paragraph_id or "") not in done]
    print(f"Already done: {len(done)} | Remaining: {len(remaining)}", flush=True)
    if not remaining:
        print("Nothing to do.", flush=True)
        return

    judge = TranslationJudge(config)
    write_lock = threading.Lock()
    progress_bar = None
    try:
        from tqdm.auto import tqdm
        progress_bar = tqdm(total=len(remaining), desc="judge-v1", unit="unit", dynamic_ncols=True)
    except ImportError:
        progress_bar = None

    results: list[JudgeResult] = [None] * len(remaining)  # type: ignore[list-item]
    workers = max(1, config.max_workers)
    start = time.time()
    with records_path.open("a", encoding="utf-8", newline="\n") as stream:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(judge.judge, rec): idx for idx, rec in enumerate(remaining)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = JudgeResult(record=remaining[idx], score=None, error=str(error))
                results[idx] = result
                rec = result.record
                with write_lock:
                    stream.write(canonical_json({
                        "instance_id": rec.instance_id,
                        "source_id": rec.source_id,
                        "source_split": rec.source_split,
                        "language": rec.language,
                        "unit": rec.unit,
                        "paragraph_id": rec.paragraph_id,
                        "source_text": rec.source_text,
                        "candidate_text": rec.candidate_text,
                        "ground_truth": rec.ground_truth,
                        "context_question": rec.context_question,
                        "score": result.score,
                        "judge_text": result.judge_text,
                        "reasoning": result.reasoning,
                        "error": result.error,
                    }) + "\n")
                    stream.flush()
                if progress_bar is not None:
                    progress_bar.update(1)
    if progress_bar is not None:
        progress_bar.close()

    elapsed = time.time() - start
    report = build_report(results, model_name=config.model_name)
    report.retry_count = judge.retry_count
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")
    report_path.write_text(json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone in {elapsed:.1f}s", flush=True)
    print(f"  total={report.total_units} judged={report.judged_units} failed={report.failed_units} retries={report.retry_count}", flush=True)
    print(f"  overall_score_mean={report.overall_score_mean}", flush=True)


def _report_to_dict(report):
    from dataclasses import asdict
    return asdict(report)


if __name__ == "__main__":
    main()

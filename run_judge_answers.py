#!/usr/bin/env python3
"""Run the LLM-as-judge on v2 answer translations (train + validation combined).

Only judges 'answer' units, using the English answer as source text and the
English question as context, with a dedicated answer-scoring prompt.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xhotpotqa.data.io import read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.judge import (
    JudgeConfig,
    JudgeResult,
    TranslationJudge,
    build_report,
    load_source_records,
    sample_units,
)
from xhotpotqa.data.io import canonical_json
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "configs" / "evaluation" / "judge_glm52.yaml"
PROCESSED = BASE / "data" / "processed"


def main() -> None:
    config = JudgeConfig.from_yaml(CONFIG)
    source_paths = {
        "train": Path(config.source_train) if config.source_train else None,
        "validation": Path(config.source_validation) if config.source_validation else None,
    }
    source_records = load_source_records(source_paths)
    print(f"source records loaded: {len(source_records)}", flush=True)

    instances: list[XHotpotInstance] = []
    for split in ("train", "validation"):
        input_path = PROCESSED / f"{split}.v2.jsonl"
        split_instances = [XHotpotInstance.from_dict(item) for item in read_jsonl(input_path)]
        print(f"{split}: {len(split_instances)} instances", flush=True)
        instances.extend(split_instances)
    print(f"total instances: {len(instances)}", flush=True)

    all_records = sample_units(
        instances,
        source_records,
        paragraph_per_lang=config.paragraph_sample_per_lang,
        question_per_lang=config.question_sample_per_lang,
        seed=config.seed,
    )
    records = [r for r in all_records if r.unit == "answer"]
    print(f"answer units to judge: {len(records)}", flush=True)

    output_path = PROCESSED / "judge_answers"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records_path = output_path.with_suffix(output_path.suffix + ".records.jsonl")

    judge = TranslationJudge(config)
    write_lock = threading.Lock()
    progress_bar = None
    try:
        from tqdm.auto import tqdm
        progress_bar = tqdm(total=len(records), desc="judge-answers", unit="ans", dynamic_ncols=True)
    except ImportError:
        progress_bar = None

    results: list[JudgeResult] = [None] * len(records)  # type: ignore[list-item]
    workers = max(1, config.max_workers)
    start = time.time()
    with records_path.open("w", encoding="utf-8", newline="\n") as stream:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(judge.judge, rec): idx for idx, rec in enumerate(records)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = JudgeResult(record=records[idx], score=None, error=str(error))
                results[idx] = result
                rec = result.record
                with write_lock:
                    stream.write(canonical_json({
                        "instance_id": rec.instance_id,
                        "source_id": rec.source_id,
                        "source_split": rec.source_split,
                        "language": rec.language,
                        "unit": rec.unit,
                        "source_text": rec.source_text,
                        "candidate_text": rec.candidate_text,
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

#!/usr/bin/env python3
"""Resume the LLM-as-judge on v2 paragraph+question units (append mode).

Only judges units not already present in judge_all.records.jsonl.
Appends results to the same file (streaming save).
"""
import sys
import time
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xhotpotqa.data.io import read_jsonl, canonical_json
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.judge import (
    JudgeConfig,
    JudgeResult,
    TranslationJudge,
    build_report,
    load_source_records,
    sample_units,
)

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "configs" / "evaluation" / "judge_glm52.yaml"
PROCESSED = BASE / "data" / "processed"
RECORDS_PATH = PROCESSED / "judge_all.records.jsonl"


def main() -> None:
    config = JudgeConfig.from_yaml(CONFIG)
    source_paths = {
        "train": Path(config.source_train) if config.source_train else None,
        "validation": Path(config.source_validation) if config.source_validation else None,
    }
    source_records = load_source_records(source_paths)

    instances: list[XHotpotInstance] = []
    for split in ("train", "validation"):
        instances.extend(
            XHotpotInstance.from_dict(item)
            for item in read_jsonl(PROCESSED / f"{split}.v2.jsonl")
        )

    all_records = sample_units(
        instances,
        source_records,
        paragraph_per_lang=config.paragraph_sample_per_lang,
        question_per_lang=config.question_sample_per_lang,
        seed=config.seed,
    )
    pq = [r for r in all_records if r.unit != "answer"]

    done: set[tuple[str, str, str]] = set()
    if RECORDS_PATH.exists():
        with RECORDS_PATH.open() as f:
            for line in f:
                r = json.loads(line)
                done.add((r["instance_id"], r["unit"], r.get("paragraph_id") or ""))

    records = [r for r in pq if (r.instance_id, r.unit, r.paragraph_id or "") not in done]
    print(f"already done: {len(done)} | remaining: {len(records)}", flush=True)
    if not records:
        print("Nothing to do.", flush=True)
        return

    judge = TranslationJudge(config)
    write_lock = threading.Lock()
    progress_bar = None
    try:
        from tqdm.auto import tqdm
        progress_bar = tqdm(total=len(records), desc="judge-resume", unit="unit", dynamic_ncols=True)
    except ImportError:
        progress_bar = None

    results: list[JudgeResult] = [None] * len(records)  # type: ignore[list-item]
    workers = max(1, config.max_workers)
    start = time.time()
    with RECORDS_PATH.open("a", encoding="utf-8", newline="\n") as stream:
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
                        "paragraph_id": rec.paragraph_id,
                        "source_text": rec.source_text,
                        "candidate_text": rec.candidate_text,
                        "ground_truth": rec.ground_truth,
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
    print(f"\nResume done in {elapsed:.1f}s", flush=True)
    print(f"  judged={report.judged_units} failed={report.failed_units} retries={report.retry_count}", flush=True)
    print(f"  batch_score_mean={report.overall_score_mean}", flush=True)


if __name__ == "__main__":
    main()

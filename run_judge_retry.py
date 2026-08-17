#!/usr/bin/env python3
"""Retry failed v2 judge units (score is None)."""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xhotpotqa.data.io import canonical_json, read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.judge import (
    JudgeConfig,
    JudgeRecord,
    JudgeResult,
    JUDGE_UNIT_ANSWER,
    JUDGE_UNIT_PARAGRAPH,
    JUDGE_UNIT_QUESTION,
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
        instances.extend(XHotpotInstance.from_dict(item) for item in read_jsonl(PROCESSED / f"{split}.v2.jsonl"))

    all_records = sample_units(
        instances, source_records,
        paragraph_per_lang=config.paragraph_sample_per_lang,
        question_per_lang=config.question_sample_per_lang,
        seed=config.seed,
    )
    pq = [r for r in all_records if r.unit != "answer"]

    # Find failed units in existing file
    failed_keys: set[tuple[str, str, str]] = set()
    if RECORDS_PATH.exists():
        with RECORDS_PATH.open() as f:
            for line in f:
                r = json.loads(line)
                if r["score"] is None:
                    failed_keys.add((r["instance_id"], r["unit"], r.get("paragraph_id") or ""))

    # Match failed keys to records
    records = [r for r in pq if (r.instance_id, r.unit, r.paragraph_id or "") in failed_keys]
    print(f"failed to retry: {len(records)}", flush=True)
    if not records:
        print("Nothing to retry.", flush=True)
        return

    judge = TranslationJudge(config)
    write_lock = threading.Lock()
    progress_bar = None
    try:
        from tqdm.auto import tqdm
        progress_bar = tqdm(total=len(records), desc="judge-retry", unit="unit", dynamic_ncols=True)
    except ImportError:
        progress_bar = None

    # Build a map of line index -> key for in-place replacement
    results: list[JudgeResult] = [None] * len(records)  # type: ignore[list-item]
    workers = max(1, config.max_workers)
    start = time.time()

    # Write new results to a temp file, then merge
    retry_path = RECORDS_PATH.with_suffix(".retry.jsonl")
    with retry_path.open("w", encoding="utf-8", newline="\n") as stream:
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

    # Merge: replace failed lines with retried results
    retry_map: dict[tuple[str, str, str], dict] = {}
    with retry_path.open() as f:
        for line in f:
            r = json.loads(line)
            retry_map[(r["instance_id"], r["unit"], r.get("paragraph_id") or "")] = r

    merged_path = RECORDS_PATH.with_suffix(".merged.jsonl")
    written = 0
    replaced = 0
    with RECORDS_PATH.open() as fin, merged_path.open("w", encoding="utf-8", newline="\n") as fout:
        for line in fin:
            r = json.loads(line)
            key = (r["instance_id"], r["unit"], r.get("paragraph_id") or "")
            if key in retry_map and r["score"] is None:
                new_r = retry_map[key]
                if new_r["score"] is not None:
                    fout.write(canonical_json(new_r) + "\n")
                    replaced += 1
                    written += 1
                    continue
            fout.write(line)
            written += 1

    import os
    os.replace(merged_path, RECORDS_PATH)
    retry_path.unlink(missing_ok=True)

    elapsed = time.time() - start
    report = build_report(results, model_name=config.model_name)
    print(f"\nRetry done in {elapsed:.1f}s", flush=True)
    print(f"  attempted={report.total_units} scored={report.judged_units} still_failed={report.failed_units}", flush=True)
    print(f"  merged: {replaced} lines replaced in {RECORDS_PATH.name}", flush=True)


if __name__ == "__main__":
    main()

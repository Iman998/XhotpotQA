#!/usr/bin/env python3
"""Run the LLM-as-judge on v2 translation data (train + validation combined)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xhotpotqa.data.io import read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.judge import JudgeConfig, load_source_questions, run_judge

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "configs" / "evaluation" / "judge_glm52.yaml"
PROCESSED = BASE / "data" / "processed"


def main() -> None:
    config = JudgeConfig.from_yaml(CONFIG)
    source_paths = {
        "train": Path(config.source_train) if config.source_train else None,
        "validation": Path(config.source_validation) if config.source_validation else None,
    }
    source_questions = load_source_questions(source_paths)
    print(f"source questions loaded: {len(source_questions)}", flush=True)

    instances: list[XHotpotInstance] = []
    for split in ("train", "validation"):
        input_path = PROCESSED / f"{split}.v2.jsonl"
        split_instances = [XHotpotInstance.from_dict(item) for item in read_jsonl(input_path)]
        print(f"{split}: {len(split_instances)} instances", flush=True)
        instances.extend(split_instances)
    print(f"total instances: {len(instances)}", flush=True)

    output_path = PROCESSED / "judge_all"
    print(f"\n=== Judging combined train+validation ===", flush=True)
    print(f"output: {output_path}", flush=True)

    start = time.time()
    report = run_judge(
        instances,
        config,
        source_questions=source_questions,
        output_path=output_path,
        progress=True,
    )
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s", flush=True)
    print(
        f"  total_units={report.total_units} judged={report.judged_units} "
        f"failed={report.failed_units} retries={report.retry_count}",
        flush=True,
    )
    print(
        f"  overall ref_mean={report.overall_score_ref_mean} "
        f"noref_mean={report.overall_score_noref_mean}",
        flush=True,
    )
    print("\nAll judging complete.", flush=True)


if __name__ == "__main__":
    main()

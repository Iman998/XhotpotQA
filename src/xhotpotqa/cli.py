"""Command-line interface; each command delegates to one application service."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from xhotpotqa.data.assignment import LanguageAssigner
from xhotpotqa.data.io import read_instances, read_jsonl
from xhotpotqa.data.plus import load_qa_translations, write_plus_instances
from xhotpotqa.data.release import upload_dataset
from xhotpotqa.data.validation import EXPECTED_SPLIT_COUNTS, validate_instances
from xhotpotqa.evaluation.evaluator import evaluate
from xhotpotqa.generation.audit import PrivateJsonlAuditLog
from xhotpotqa.generation.config import GenerationConfig
from xhotpotqa.generation.openai_compatible import OpenAICompatibleGenerator
from xhotpotqa.generation.pipeline import XHotpotBuilder
from xhotpotqa.generation.run import generate_dataset, load_hotpot_records
from xhotpotqa.generation.translation import StructuredTranslator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xhotpotqa")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate canonical dataset files")
    validate.add_argument("--train", type=Path)
    validate.add_argument("--validation", type=Path)
    validate.add_argument("--strict-release", action="store_true")

    generate = commands.add_parser("generate-v2", help="generate a Gemma 4 translation release")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--config", type=Path, required=True)
    generate.add_argument("--split", choices=("train", "validation"), required=True)
    generate.add_argument(
        "--audit-log",
        type=Path,
        help="optional private JSONL log containing requests and raw model responses",
    )

    expand = commands.add_parser(
        "expand-plus",
        help="create the 24 parallel question-answer views of XHotpotQA+",
    )
    expand.add_argument("--base", type=Path, required=True)
    expand.add_argument("--translations", type=Path, required=True)
    expand.add_argument("--output", type=Path, required=True)
    expand.add_argument("--split", choices=("train", "validation"), required=True)
    expand.add_argument(
        "--strict-release",
        action="store_true",
        help="require the canonical base and expanded split cardinalities",
    )

    evaluation = commands.add_parser("evaluate", help="evaluate answers and supporting facts")
    evaluation.add_argument("--gold", type=Path, required=True)
    evaluation.add_argument("--predictions", type=Path, required=True)
    evaluation.add_argument("--output", type=Path, required=True)

    upload = commands.add_parser("upload-hf", help="validate and upload a public HF release")
    upload.add_argument("--train", type=Path, required=True)
    upload.add_argument("--validation", type=Path, required=True)
    upload.add_argument("--plus-train", type=Path, required=True)
    upload.add_argument("--plus-validation", type=Path, required=True)
    upload.add_argument("--card", type=Path, default=Path("dataset_card/README.md"))
    upload.add_argument("--repo-id", default="iman998/XHotpotQA")
    upload.add_argument(
        "--dry-run", action="store_true", help="validate release inputs without network access"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    if args.command == "generate-v2":
        return _generate(args)
    if args.command == "expand-plus":
        return _expand_plus(args)
    if args.command == "evaluate":
        return _evaluate(args)
    if args.command == "upload-hf":
        upload_dataset(
            args.train,
            args.validation,
            args.plus_train,
            args.plus_validation,
            args.card,
            repo_id=args.repo_id,
            dry_run=args.dry_run,
        )
        print(json.dumps({"validated": True, "uploaded": not args.dry_run}))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def _validate(args: argparse.Namespace) -> int:
    any_error = False
    for split in ("train", "validation"):
        path: Path | None = getattr(args, split)
        if path is None:
            continue
        expected = EXPECTED_SPLIT_COUNTS[split] if args.strict_release else None
        report = validate_instances(
            read_instances(path),
            expected_count=expected,
            expected_split=split,
            strict_release=args.strict_release,
        )
        print(json.dumps({"split": split, **report.__dict__}, ensure_ascii=False, default=list))
        any_error |= not report.ok
    return int(any_error)


def _generate(args: argparse.Namespace) -> int:
    config = GenerationConfig.from_yaml(args.config)
    generator = OpenAICompatibleGenerator(config)
    translator = StructuredTranslator(
        generator,
        model_id=config.model_id,
        revision=config.revision,
        max_retries=config.max_retries,
        decoding=config.decoding_parameters(),
        audit_writer=PrivateJsonlAuditLog(args.audit_log) if args.audit_log else None,
    )
    builder = XHotpotBuilder(translator, LanguageAssigner(config.seed))
    written = generate_dataset(
        load_hotpot_records(args.input, args.split),
        args.output,
        args.split,
        builder,
        checkpoint_every=config.checkpoint_every,
    )
    print(json.dumps({"written": written, "output": str(args.output)}))
    return 0


def _expand_plus(args: argparse.Namespace) -> int:
    expected_base_count = EXPECTED_SPLIT_COUNTS[args.split] if args.strict_release else None
    report = write_plus_instances(
        args.output,
        read_instances(args.base),
        load_qa_translations(args.translations),
        expected_base_count=expected_base_count,
        expected_split=args.split,
    )
    print(
        json.dumps(
            {
                "base_records": report.base_count,
                "variants": report.variant_count,
                "languages_per_instance": report.languages_per_instance,
                "output": str(args.output),
            }
        )
    )
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    predictions: dict[str, dict[str, Any]] = {}
    for item in read_jsonl(args.predictions):
        prediction_id = item.get("id")
        if not isinstance(prediction_id, str) or not prediction_id:
            raise ValueError("Every prediction must have a non-empty string id")
        if prediction_id in predictions:
            raise ValueError(f"Duplicate prediction id: {prediction_id!r}")
        predictions[prediction_id] = item
    report = evaluate(read_instances(args.gold), predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False))
    return 0

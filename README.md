# XHotpotQA

**XHotpotQA** is a translation-derived benchmark for cross-lingual multi-hop question
answering over mixed-language evidence. Each question–answer pair has one language while
each candidate paragraph receives an independently assigned language. The benchmark keeps
HotpotQA's fixed distractor candidates and sentence-level supporting-fact supervision, so
retrieval/selection, reading, and end-to-end reasoning can be evaluated separately.

| Property | Value |
|---|---:|
| Languages | 24 |
| Public audited V1 dataset | 15,661 train / 7,405 validation |
| Frozen data revision | `52b8bee41ff2bb0d41cd400ff5646c0e800b5127` |
| Audited raw parallel train views | 375,864 |
| Audited raw validation views | 7,405 |
| Complete XHotpotQA+ target | 553,584 views (not yet complete) |
| Source task | HotpotQA distractor |
| Dataset license | CC BY-SA 4.0 |

> **Public audited V1 dataset:**
> [`Iman998/XhotpotQA`](https://huggingface.co/datasets/Iman998/XhotpotQA), configuration
> `xhotpotqa_v1_audited`. For reproducible experiments, pin data revision
> [`52b8bee41ff2bb0d41cd400ff5646c0e800b5127`](https://huggingface.co/datasets/Iman998/XhotpotQA/tree/52b8bee41ff2bb0d41cd400ff5646c0e800b5127).
> This public dataset is an audit-preserving recovery of V1:
> all 15,661 train sources and all 7,405 validation sources are retained, and each row
> exposes `status` plus `structural_flags`. A quarantined status identifies a known
> structural defect; it does not remove the row.
>
> The strict canonical `xhotpotqa` and `xhotpotqa_plus` configurations remain
> prospective. In particular, the 177,720-view parallel validation mapping required for
> XHotpotQA+ is not present in the audited archive. Canonical V2 data are also pending a
> completed generation and paired quality audit.

## Why this benchmark?

Translating an entire QA example into one language does not test whether a model can bridge
facts written in different languages. XHotpotQA controls the language of the question,
bridge evidence, answer-bearing evidence, and distractors independently. This makes it
possible to measure query–evidence mismatch, cross-hop composition, and irrelevant-language
interference without conflating them with full-corpus retrieval.

## Installation

```bash
git clone https://github.com/Iman998/XhotpotQA.git
cd XhotpotQA
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Install the lightweight OpenAI-compatible client only when generating V2:

```bash
pip install -e ".[generation]"
```

## Load the frozen public dataset

```python
from collections import Counter
from datasets import load_dataset

DATA_REVISION = "52b8bee41ff2bb0d41cd400ff5646c0e800b5127"

dataset = load_dataset(
    "Iman998/XhotpotQA",
    "xhotpotqa_v1_audited",
    revision=DATA_REVISION,
)

validation = dataset["validation"]
print(len(dataset["train"]), len(validation))  # 15_661, 7_405
print(Counter(validation["status"]))
print(validation[0]["question_language"], validation[0]["structural_flags"])
```

Quarantined records intentionally remain part of the complete benchmark denominator. If a
study also reports an accepted-only sensitivity result, filter explicitly and report the
resulting row count:

```python
accepted_validation = validation.filter(lambda row: row["status"] == "accepted")
print(accepted_validation.num_rows)
```

The pinned revision identifies the published audited-V1 data snapshot even if the Hub card
later receives documentation-only updates. The exact recovered-Parquet schema, provenance
fields, status semantics, and release
limitations are documented in the
[`dataset_card/README.md`](dataset_card/README.md). The schema in
[`docs/SCHEMA.md`](docs/SCHEMA.md) is the stricter canonical JSONL contract used by the
prospective V2 and XHotpotQA+ pipeline; it is not a claim that the recovered V1 rows have
already passed those strict gates.

## Rebuild the public audited V1

The public Parquet release is built directly from the two pinned HotpotQA source files and
the recovered pandas-column translation shards. The standalone builder requires `ijson`
for streaming JSON and `pyarrow` for Parquet:

```bash
python -m pip install ijson pyarrow
```

Set `SOURCE_DIR` to the directory containing the official HotpotQA JSON files and
`RAW_DIR` to the recovered cross-lingual shard directory. Pass every repeated shard
argument in exactly the order shown:

```bash
SOURCE_DIR=/path/to/hotpotqa
RAW_DIR=/path/to/cross-lingual

python scripts/build_hf_public_v1.py \
  --train-source "$SOURCE_DIR/hotpot_train_v1.1.json" \
  --validation-source "$SOURCE_DIR/hotpot_dev_distractor_v1.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_0-1.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_1-2.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_2-3.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_3-4.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_4-5.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_5-6.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_6-7.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_7-8.json" \
  --train-shard "$RAW_DIR/hotpot_train_translate_8-end.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_0-1.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_1-2.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_2-3.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_3-4.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_4-5.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_5-6.json" \
  --validation-shard "$RAW_DIR/hotpot_validation_translate_6-end.json" \
  --output-dir build/hf_public_v1 \
  --rows-per-shard 5000
```

The script hash-pins all 18 inputs—the two source snapshots plus 16 translation shards—and
rejects unexpected basenames, order, byte sizes, SHA-256 values, duplication, or changes
during the build. The output directory must not already exist; data are built in a temporary
sibling directory, read back for validation, and moved into place only after all checks pass.

Expected output:

```text
build/hf_public_v1/
├── RELEASE_MANIFEST.json
└── data/
    └── xhotpotqa_v1_audited/
        ├── train-*.parquet       # 15,661 rows
        └── validation-*.parquet  # 7,405 rows
```

The manifest records the `xhotpotqa_v1_audited` configuration, 23,066 total rows,
ordered input roles and hashes, status/flag/language counts, Parquet file hashes, builder
version and script hash, Git revision including dirty state, and the Python/platform/library
environment. The builder writes data and the manifest. When reproducing the published
snapshot in another Hub repository, stage the reviewed `dataset_card/README.md` as its
repository-level `README.md`.

## Build the parallel XHotpotQA+ views

XHotpotQA+ pairs every canonical base instance with all 24 available question--answer
languages while holding the ordered candidate evidence and supporting-fact annotations fixed.
A complete mapping would produce 375,864 training views and 177,720 validation views
(553,584 total). The expansion itself is deterministic and does not call a model. The audited
archive currently contains only the training-side parallel views, so publication of the
separate `xhotpotqa_plus` Hub configuration remains blocked. The strict
`xhotpotqa` configuration is likewise prospective. The public audited-V1 repository has
`xhotpotqa_v1_audited` as its sole and default configuration.

Provide translations as either a source-ID keyed JSON object or the line-oriented JSONL form
documented in [`docs/XHOTPOTQA_PLUS.md`](docs/XHOTPOTQA_PLUS.md), then run:

```bash
xhotpotqa expand-plus \
  --base data/processed/validation.jsonl \
  --translations data/processed/qa-translations.validation.jsonl \
  --output data/processed/xhotpotqa-plus.validation.jsonl \
  --split validation \
  --strict-release
```

For each view, `source_id` is retained and the immutable variant ID is
`<base-id>--qa-<language>`. Base provenance, evidence, and supervision are copied exactly;
the semantic SHA-256 checksum is recomputed after replacing the question, answer, and their
language code. The command validates all 24 languages for every source, rejects unmatched or
duplicate source IDs, and writes atomically so a failed validation cannot replace an existing
release. Preserve the translation mapping's checksum and generation metadata separately:
inherited record provenance describes the base record, not that external mapping.

## Validate a local release

```bash
xhotpotqa validate \
  --train data/processed/train.jsonl \
  --validation data/processed/validation.jsonl \
  --strict-release
```

## Audit and import the historical shards

The original pandas-column JSON shards do not contain source IDs or support annotations.
Import them only through an ordered join to a pinned HotpotQA JSON array:

```bash
xhotpotqa import-legacy \
  --shard data/raw/hotpot_validation_translate_0-1.json \
  --shard data/raw/hotpot_validation_translate_1-2.json \
  --source data/source/hotpot_dev_distractor_v1.json \
  --output-dir data/audited/validation \
  --split validation \
  --expected-source-sha256 <sha256> \
  --expected-source-order-sha256 <sha256>
```

Repeat `--shard` in historical order. The command streams large inputs, materializes stable
source IDs, and writes `canonical.jsonl`, `raw_manifest.json`, a quarantine manifest, and a
content-addressed correction manifest. It exits nonzero while any record is quarantined and
refuses to overwrite an existing import directory. See
[`docs/LEGACY_IMPORT.md`](docs/LEGACY_IMPORT.md).

## Generate XHotpotQA V2 with any OpenAI-compatible model

The V2 pipeline is model-agnostic. It sends a strict JSON translation contract to any model
already exposed through an OpenAI-compatible chat-completions endpoint. The data process is
a lightweight client and never loads model weights itself. Each user payload includes an
explicit JSON `response_schema`: single units must return only a non-empty `translation`
string, while sentence arrays must return only a `translations` array with exactly the same
cardinality as the input. The frozen prompt identity is recorded in every generated record.
Its SHA-256 covers the canonical prompt specification---the system message plus both request
and response-schema templates---rather than the system text alone. The parser removes only
surrounding whitespace: prose, Markdown fences, wrapper objects, duplicate keys, and multiple
JSON values are rejected and retried.

For example, start any compatible checkpoint with vLLM (replace all angle-bracket values):

```bash
vllm serve <checkpoint> \
  --served-model-name <model-id> \
  --tensor-parallel-size <n> \
  --max-model-len <tokens>
```

Point the client at the server without placing credentials in config files:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=EMPTY  # use a real secret only when the endpoint requires it
```

```bash
xhotpotqa generate-v2 \
  --input data/raw/hotpot_train_v1.1.json \
  --output data/processed/train.v2.jsonl \
  --config configs/generation/openai_compatible.yaml \
  --split train \
  --difficulty hard \
  --max-workers 8 \
  --assignment-manifest data/manifests/v1.train.assignments.json \
  --audit-log private-audit/train.v2.responses.jsonl
```

`--assignment-manifest` is optional. Use it for the corrective V2 run to preserve every V1
question--answer and paragraph language exactly; omit it to retain the seeded `sha256-hash-v1`
assignment path. The manifest schema, strict validation rules, and paired-audit key are defined
in [`docs/ASSIGNMENT_MANIFEST.md`](docs/ASSIGNMENT_MANIFEST.md).

Difficulty filtering is explicit: omit `--difficulty` to process every source record. Parallel
generation bounds in-flight requests and writes successful records in input order. A sidecar
lock rejects a second writer for the same output, and the atomically replaced
`*.errors.jsonl` ledger retains only unresolved failures. Any unresolved record makes the
command exit nonzero; no source text or placeholder is silently substituted for a failed
translation.

Generation is deterministic at the assignment layer and resumable by immutable source ID.
It never changes sentence order or supporting-fact indices. Model-specific chat-template
arguments are optional YAML settings, not assumptions in the client. A Gemma configuration
is included only as an example in `configs/generation/gemma4_31b.yaml`. See
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for the audit trail and server recipe.
The optional audit log contains source text and raw model output. Keep it private and outside
the public dataset; omit `--audit-log` when raw-response retention is not approved.

## Audit translation quality with an OpenAI-compatible judge

The judge uses the same environment-only connection contract. It freezes a deterministic,
language-balanced sample manifest, pairs sampled questions and answers, requires a strict JSON
score response, and compacts resumed attempts into one record per sampled unit:

```bash
xhotpotqa judge \
  --input data/processed/train.v2.jsonl \
  --input data/processed/validation.v2.jsonl \
  --source-train data/raw/hotpot_train_v1.1.json \
  --source-validation data/raw/hotpot_dev_distractor_v1.json \
  --output outputs/translation-judge \
  --config configs/evaluation/openai_compatible.yaml
```

The resulting `.sample.jsonl`, `.records.jsonl`, and `.report.json` artifacts record the model
alias, prompt version/hash, sample-manifest hash, and application retries. Hidden reasoning is
never requested or retained. Use a new output prefix when changing the model, prompt, inputs,
or sampling configuration.

## Evaluate predictions

Prediction JSONL records contain an `id`, `answer`, and a list of supporting facts. Run:

```bash
xhotpotqa evaluate \
  --gold data/processed/validation.jsonl \
  --predictions outputs/predictions.jsonl \
  --output outputs/metrics.json
```

The report includes answer EM/F1, support precision/recall/F1, Hotpot-style joint metrics,
question-language and script-relation aggregates, five principal language conditions plus a
separate no-distractor/NA condition, and stable bins/summaries for gold and distractor
mismatch, gold-evidence entropy, and the number of distinct candidate languages. Missing
predictions are scored as empty; missing and unexpected prediction counts are reported
explicitly.

## Project layout

```text
configs/                 versioned data, generation, and evaluation settings
src/xhotpotqa/data/      schema, I/O, deterministic construction, validation
src/xhotpotqa/generation/ model adapters, prompts, and resumable translation
src/xhotpotqa/evaluation/ normalization, metrics, and language stratification
scripts/                 thin, automation-friendly entry points
tests/                   unit and contract tests
dataset_card/            Hugging Face dataset card
docs/                    schema, data statement, and reproducibility protocol
```

## Reproducibility and integrity

- No credentials are accepted as command-line arguments or stored in configuration files.
- The audited V1 release payload selects one train view per 24-view source group using a stable
  source-ID-keyed SHA-256 rule and retains the sole recovered validation view. This is a
  reproducible public projection, not a reconstruction of the lost historical random seed.
- The audited release builder rejects renamed, reordered, missing, duplicated, or
  checksum-mismatched source inputs. It preserves detected defects through `status` and
  `structural_flags` instead of silently rewriting or dropping rows.
- `RELEASE_MANIFEST.json` records split counts, status and flag totals, question-language
  counts, and every Parquet shard's row count, byte size, and SHA-256.
- V2 can replay a checksum-pinned V1 assignment manifest for paired quality analysis. When no
  manifest is supplied, assignments are derived from `seed + source_id + unit_id`, so
  sharding does not alter them.
- Canonical JSONL output records contain generation provenance and a versioned SHA-256
  semantic checksum.

## Prospective strict canonical release

The `upload-hf` command belongs to the prospective strict JSONL release path. It requires
both canonical base splits and both complete XHotpotQA+ splits, blocks unless their counts are
exactly 15,661/7,405 and 375,864/177,720, and validates schema, IDs, language codes,
support indices, answer language, checksums, and base-to-parallel invariants.

Preflight that future release without credentials or network access:

```bash
xhotpotqa upload-hf \
  --train data/processed/train.jsonl \
  --validation data/processed/validation.jsonl \
  --plus-train data/processed/xhotpotqa-plus.train.jsonl \
  --plus-validation data/processed/xhotpotqa-plus.validation.jsonl \
  --card path/to/canonical-release-card.md \
  --dry-run
```

The current `dataset_card/README.md` declares the audited Parquet configuration and is
deliberately not a canonical JSONL release card. The strict preflight verifies that its
dedicated card declares the exact JSONL paths and that each parallel view preserves its base
record's evidence, supervision, and provenance. A future canonical upload uses one Hub commit
for its card, integrity manifest, and all four validated split files.

## License and attribution

Code is MIT-licensed. Dataset files are adaptations of HotpotQA and use **CC BY-SA 4.0**.
Users must attribute both XHotpotQA and the original HotpotQA authors, preserve ShareAlike
terms, and consult the data statement before deployment.

## Citation

```bibtex
@misc{barati2026xhotpotqa,
  title   = {XHotpotQA: A Benchmark for Cross-Lingual Multi-Hop Question
             Answering over Mixed-Language Evidence},
  author  = {Barati, Iman and Ghafouri, Arash and Minaei-Bidgoli, Behrouz},
  year    = {2026},
  howpublished = {Hugging Face dataset},
  url     = {https://huggingface.co/datasets/Iman998/XhotpotQA},
  note    = {Audited V1 data snapshot, revision
             52b8bee41ff2bb0d41cd400ff5646c0e800b5127; manuscript in preparation}
}
```

The persistent manuscript archive and version-history identifier are pending deposit. This
notice will be replaced with the exact archive record after it has been minted.

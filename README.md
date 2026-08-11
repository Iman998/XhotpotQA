# XHotpotQA

**XHotpotQA** is a translation-derived benchmark for cross-lingual multi-hop question
answering over mixed-language evidence. Each question–answer pair has one language while
each candidate paragraph receives an independently assigned language. The benchmark keeps
HotpotQA's fixed distractor candidates and sentence-level supporting-fact supervision, so
retrieval/selection, reading, and end-to-end reasoning can be evaluated separately.

| Property | Value |
|---|---:|
| Languages | 24 |
| Historical base sources | 15,661 train / 7,405 validation |
| Audited raw parallel train views | 375,864 |
| Audited raw validation views | 7,405 |
| Complete XHotpotQA+ target | 553,584 views (not yet complete) |
| Source task | HotpotQA distractor |
| Dataset license | CC BY-SA 4.0 |

> **Release status:** the public dataset deposit and persistent manuscript archive are
> pending. The strict importer currently quarantines structurally invalid legacy records,
> and the 177,720-view XHotpotQA+ validation split is not present in the audited archive.
> Hub-loading commands become operational only after those release gates pass.

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

## Load the data after publication

```python
from datasets import load_dataset

dataset = load_dataset("iman998/XHotpotQA")
parallel = load_dataset("iman998/XHotpotQA", "xhotpotqa_plus")
print(dataset["validation"][0])
print(parallel["validation"][0])
```

The canonical record schema is documented in [`docs/SCHEMA.md`](docs/SCHEMA.md). Every
release is validated before upload; the validator checks exact split sizes, unique IDs,
language codes, sentence indices, answer language, and content checksums.

## Build the parallel XHotpotQA+ views

XHotpotQA+ pairs every canonical base instance with all 24 available question--answer
languages while holding the ordered candidate evidence and supporting-fact annotations fixed.
A complete mapping would produce 375,864 training views and 177,720 validation views
(553,584 total). The expansion itself is deterministic and does not call a model. The audited
archive currently contains only the training-side parallel views, so publication of the
separate `xhotpotqa_plus` Hub configuration remains blocked; `xhotpotqa` is the intended default.

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
a lightweight client and never loads model weights itself.

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
  --audit-log private-audit/train.v2.responses.jsonl
```

Generation is deterministic at the assignment layer and resumable by immutable source ID.
It never changes sentence order or supporting-fact indices. Model-specific chat-template
arguments are optional YAML settings, not assumptions in the client. A Gemma configuration
is included only as an example in `configs/generation/gemma4_31b.yaml`. See
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for the audit trail and server recipe.
The optional audit log contains source text and raw model output. Keep it private and outside
the public dataset; omit `--audit-log` when raw-response retention is not approved.

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
- The audited V1 validation mapping and 24-view training groups are preserved; the exact
  historical base-train projection remains blocked on the consolidated server manifest. V2
  assignments are derived from `seed + source_id + unit_id`, so sharding does not alter them.
- Every output record contains generation provenance and a versioned SHA-256 semantic checksum.
- Upload is blocked unless base counts are exactly 15,661/7,405 and parallel-view counts are
  exactly 375,864/177,720.
- The release pipeline rejects unsupported language codes, duplicate IDs, broken support
  indices, and question/answer language disagreement.

Preflight a Hugging Face release without credentials or network access:

```bash
xhotpotqa upload-hf \
  --train data/processed/train.jsonl \
  --validation data/processed/validation.jsonl \
  --plus-train data/processed/xhotpotqa-plus.train.jsonl \
  --plus-validation data/processed/xhotpotqa-plus.validation.jsonl \
  --card dataset_card/README.md \
  --dry-run
```

The preflight also verifies that the card declares the exact JSONL paths uploaded by the
release command and that each parallel view preserves its base record's evidence, supervision,
and provenance. A real upload uses one Hub commit for the card, integrity manifest, and all
four validated split files. The generated manifest records configuration and split paths,
record counts, byte sizes and SHA-256 hashes, the toolkit/data version, the code revision, and
the `pyproject.toml` hash.

## License and attribution

Code is MIT-licensed. Dataset files are adaptations of HotpotQA and use **CC BY-SA 4.0**.
Users must attribute both XHotpotQA and the original HotpotQA authors, preserve ShareAlike
terms, and consult the data statement before deployment.

## Citation

```bibtex
@unpublished{barati2026xhotpotqa,
  title   = {XHotpotQA: A Benchmark for Cross-Lingual Multi-Hop Question
             Answering over Mixed-Language Evidence},
  author  = {Barati, Iman and Ghafouri, Arash and Minaei-Bidgoli, Behrouz},
  year    = {2026},
  note    = {Manuscript and resource release in preparation}
}
```

The persistent manuscript archive and version-history identifier are pending deposit. This
notice will be replaced with the exact archive record after it has been minted.

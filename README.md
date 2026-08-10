# XHotpotQA

**XHotpotQA** is a translation-derived benchmark for cross-lingual multi-hop question
answering over mixed-language evidence. Each question–answer pair has one language while
each candidate paragraph receives an independently assigned language. The benchmark keeps
HotpotQA's fixed distractor candidates and sentence-level supporting-fact supervision, so
retrieval/selection, reading, and end-to-end reasoning can be evaluated separately.

| Property | Value |
|---|---:|
| Languages | 24 |
| Base instances | 23,066 |
| Train / validation | 15,661 / 7,405 |
| Derivable XHotpotQA+ parallel views | 553,584 |
| Source task | HotpotQA distractor |
| Dataset license | CC BY-SA 4.0 |

> **Release status:** the public dataset deposit and persistent manuscript archive are
> pending. This repository documents the release candidate; Hub-loading commands become
> operational after the dataset is published.

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
This produces 375,864 training views and 177,720 validation views (553,584 total). The
expansion is a deterministic data transformation and does not call a model. These views are
published as the separate `xhotpotqa_plus` Hub configuration; `xhotpotqa` remains the default.

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

## Generate XHotpotQA V2 with Gemma 4 31B

The V2 pipeline assumes Google's official `google/gemma-4-31B-it` checkpoint is already
served by vLLM. The data process is a lightweight OpenAI-compatible client and never loads
model weights itself.

Start the server (adjust tensor parallelism and context length for your hardware):

```bash
vllm serve google/gemma-4-31B-it \
  --served-model-name google/gemma-4-31B-it \
  --tensor-parallel-size 4 \
  --max-model-len 16384 \
  --reasoning-parser gemma4 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
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
  --config configs/generation/gemma4_31b.yaml \
  --split train \
  --audit-log private-audit/train.v2.responses.jsonl
```

Generation is deterministic at the assignment layer and resumable by immutable source ID.
It never changes sentence order or supporting-fact indices. Thinking is disabled for the
translation pass so hidden reasoning is not stored in the resource. See
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
question-language and script-relation aggregates, the five language conditions, and stable
bins/summaries for gold and distractor mismatch, gold-evidence entropy, and the number of
distinct candidate languages. Missing predictions are scored as empty; missing and unexpected
prediction counts are reported explicitly.

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
- The evaluated V1 assignment is preserved by its immutable manifest. V2 assignments are
  derived from `seed + source_id + unit_id`, so sharding does not alter regenerated data.
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
  title   = {XHotpotQA: A 24-Language Benchmark for Cross-Lingual Multi-Hop
             Question Answering over Mixed-Language Evidence},
  author  = {Barati, Iman and Ghafouri, Arash and Minaei-Bidgoli, Behrouz},
  year    = {2026},
  note    = {Manuscript and resource release in preparation}
}
```

The persistent manuscript archive and version-history identifier are pending deposit. This
notice will be replaced with the exact archive record after it has been minted.

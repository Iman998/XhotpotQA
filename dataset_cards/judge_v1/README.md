---
pretty_name: XHotpotQA GLM-5.2 Translation Judge — V1
license: cc-by-sa-4.0
task_categories:
  - text-classification
language:
  - ar
  - bn
  - de
  - el
  - es
  - fa
  - fr
  - hi
  - id
  - it
  - ja
  - ko
  - nl
  - pl
  - pt
  - ru
  - sv
  - sw
  - th
  - tr
  - ur
  - vi
  - zh
tags:
  - llm-as-a-judge
  - translation-quality
  - cross-lingual
  - multi-hop-qa
  - glm-5.2
  - audited
size_categories:
  - 1K<n<10K
configs:
  - config_name: xhotpotqa_glm52_judge_v1
    data_files:
      - split: audit
        path: data/audit-*.parquet
---

<div align="center">

# XHotpotQA · GLM-5.2 Judge · V1

### Sanitized, language-balanced translation-quality audit

[![Rows](https://img.shields.io/badge/audit%20rows-2%2C760-2f80ed?style=for-the-badge)](#sampling-design)
[![Coverage](https://img.shields.io/badge/scored-100%25-2ca44f?style=for-the-badge)](#results)
[![Model identity](https://img.shields.io/badge/model-requested%20alias-orange?style=for-the-badge)](#model-provenance)
[![Snapshot](https://img.shields.io/badge/snapshot-ba891ae-7b61ff?style=for-the-badge)](https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V1/tree/ba891ae62ed989606c9fc2fd5f08f9e88ef37547)
[![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-7b61ff?style=for-the-badge)](#license)

**No hidden reasoning · no raw endpoint · no credentials · no source/candidate text duplication**

</div>

> [!NOTE]
> This dataset contains LLM-generated audit annotations, not QA-system predictions and not human gold labels. The endpoint was requested with model string `glm-5.2`; the provider-resolved model revision was not recorded.

## Overview

This release contains the complete V1 translation audit used in the XHotpotQA resource analysis. Each row evaluates one translated paragraph, question, or short answer against its English source on a 0–100 scale.

The public payload removes hidden reasoning and raw texts. Reproducible joins use stable XHotpotQA identifiers plus exact UTF-8 SHA-256 hashes of the source and candidate strings.

This V1 audit and the separately released V2 audit use independently drawn,
balanced samples. The audits are **independent and unpaired**; their mean
difference must not be interpreted as an instance-level or causal V2
improvement estimate.

The public annotation payload is frozen at Hub revision
[`ba891ae62ed989606c9fc2fd5f08f9e88ef37547`](https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V1/tree/ba891ae62ed989606c9fc2fd5f08f9e88ef37547).

## Quickstart

```python
from datasets import load_dataset

AUDIT_REVISION = "ba891ae62ed989606c9fc2fd5f08f9e88ef37547"

audit = load_dataset(
    "Iman998/XhotpotQA-GLM52-Judge-V1",
    "xhotpotqa_glm52_judge_v1",
    split="audit",
    revision=AUDIT_REVISION,
)

print(audit.num_rows)  # 2760
print(audit.features)
print(audit.filter(lambda row: row["unit"] == "paragraph")[0])
```

Join rows to the default V1.1 configuration of the pinned
[XHotpotQA snapshot](https://huggingface.co/datasets/Iman998/XhotpotQA/tree/1d29e7918cf1acc045726c70fddba82371833090)
using `instance_id`, `unit`, and `paragraph_id`. V1.1 retains the V1 translations
and adds original paragraph `source_sentences`. Verify exact joined strings with
`source_text_sha256` and `candidate_text_sha256`.

## Sampling design

Sampling was deterministic and balanced over 23 target languages.

| Unit | Per language | Total |
|---|---:|---:|
| paragraph | 80 | 1,840 |
| question | 20 | 460 |
| answer | 20 | 460 |
| **all units** | **120** | **2,760** |

- Sampling seed: `20260810`
- Train-derived units: 1,866
- Validation-derived units: 894
- Successfully scored: 2,760
- Failed final rows: 0

Paragraph source text was recovered from the pinned English HotpotQA context by source ID and title. Question and answer sources came from the original English fields.

## Results

| Unit | Count | Mean | Median | SD | Below 60 | Below 80 | At least 90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| paragraph | 1,840 | 90.913 | 94 | 9.47 | 24 | 182 | 1,358 |
| question | 460 | 93.459 | 96 | 10.71 | 12 | 35 | 387 |
| answer | 460 | 95.474 | 100 | 14.47 | 21 | 28 | 416 |
| **weighted overall** | **2,760** | **92.097** | — | — | — | — | — |

The overall mean reflects the audit allocation: two-thirds paragraphs, one-sixth questions, and one-sixth answers. Unit means are the primary quantities.

### Per-language means

| Language | Paragraph | Question | Answer | Overall |
|---|---:|---:|---:|---:|
| Arabic | 88.05 | 94.35 | 99.60 | 91.03 |
| Bengali | 89.11 | 91.95 | 99.50 | 91.32 |
| German | 93.33 | 93.95 | 89.50 | 92.79 |
| Greek | 88.30 | 96.90 | 94.75 | 90.81 |
| Spanish | 95.08 | 96.05 | 96.00 | 95.39 |
| Persian | 87.99 | 97.90 | 95.75 | 90.93 |
| French | 93.95 | 96.35 | 97.50 | 94.94 |
| Hindi | 90.84 | 90.10 | 98.75 | 92.03 |
| Indonesian | 93.12 | 92.55 | 91.50 | 92.76 |
| Italian | 94.53 | 94.95 | 98.80 | 95.31 |
| Japanese | 89.61 | 94.30 | 95.25 | 91.33 |
| Korean | 91.42 | 93.40 | 98.75 | 92.97 |
| Dutch | 91.92 | 94.20 | 95.50 | 92.90 |
| Polish | 91.35 | 93.00 | 90.75 | 91.53 |
| Portuguese | 95.44 | 98.45 | 95.00 | 95.87 |
| Russian | 86.36 | 94.05 | 98.35 | 89.64 |
| Swedish | 89.76 | 91.60 | 88.75 | 89.90 |
| Swahili | 87.78 | 90.95 | 94.25 | 89.38 |
| Thai | 90.94 | 88.70 | 96.00 | 91.41 |
| Turkish | 88.31 | 87.85 | 94.00 | 89.18 |
| Urdu | 91.04 | 92.25 | 97.50 | 92.32 |
| Vietnamese | 92.46 | 94.50 | 91.25 | 92.60 |
| Mandarin Chinese | 90.30 | 91.25 | 98.90 | 91.89 |

Machine-readable full-precision results are included in `tables/SUMMARY.json` and `tables/BY_LANGUAGE.csv`. `tables/BOOTSTRAP.json` contains the deterministic within-language-by-unit percentile bootstrap.

## Public schema

| Field | Description |
|---|---|
| `judge_record_id` | Deterministic hash of version and unit identity |
| `dataset_version`, `dataset_revision` | Source dataset locator and candidate revision |
| `instance_id`, `source_id`, `source_split` | Stable dataset identifiers |
| `target_language`, `unit`, `paragraph_id` | Audit stratum and unit identity |
| `score` | Integer source-referenced score from 0 to 100 |
| `score_origin` | Where the historical parser found the score |
| `judge_explanation` | Visible short explanation, if returned |
| `source_text_sha256`, `candidate_text_sha256` | Exact join-verification hashes |
| `requested_judge_model` | Requested API alias |
| `resolved_judge_revision` | Null because the endpoint revision was not persisted |
| `judge_prompt_version`, `judge_prompt_sha256` | Exact scoring contract identifiers |
| `raw_artifact_sha256`, `raw_line_number` | Private-archive lineage without exposing raw content |

The release does not contain `source_text`, `candidate_text`, hidden reasoning, endpoint URL, request errors, API keys, or raw logs.

## Score provenance

| Origin | Rows |
|---|---:|
| visible explicit `SCORE:` line | 2,746 |
| explicit score in reasoning fallback | 4 |
| last-integer reasoning fallback | 10 |

Fourteen rows have no visible explanation and are explicitly labeled as reasoning-derived. No reasoning text is released.

## Model provenance

| Setting | Value |
|---|---|
| Requested model string | `glm-5.2` |
| Provider-resolved revision | not recorded |
| Temperature | 0.0 |
| Seed | `20260810` |
| Maximum output tokens | 4,000 |
| Concurrent workers | 1 |
| Final completion | 2,760 of 2,760 |

The official GLM-5.2 model card documents the public model family, but it does not prove which checkpoint a third-party alias resolved to. The release therefore uses `requested_alias_only_provider_revision_not_recorded` as its identity status.

## Historical prompt contract

The historical implementation produces one source-referenced score. An early code comment describing two scores is stale and is not supported by these records.

<details>
<summary><strong>Paragraph and question system prompt</strong></summary>

```text
You are a meticulous bilingual translation judge. Your task is to assign a single integer score from 0 to 100 (0 = unusable, 100 = excellent) for a candidate translation, using only the source text and the target candidate.
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

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100.
```

SHA-256: `e939a00a58e2347b60e9dc04ad7278b88430d41e4a2aea8749023c08631db5af`

</details>

<details>
<summary><strong>Short-answer system prompt</strong></summary>

```text
You are a meticulous bilingual translation judge for short answers. You are given an English question ("context_question") and its short English answer ("text") alongside a translated answer ("model_output"). Your task is to judge how well "model_output" translates the English answer into the target language.
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

Output format: respond with a short explanation (1-3 sentences) of the strengths and weaknesses of the candidate answer translation, then on a new final line output exactly "SCORE: <integer>" where <integer> is the score from 0 to 100.
```

SHA-256: `7e560af3c545c22fee93f78f3b621326e04c92ddcd61844c79ee45994320a525`

</details>

The phrase “critical error floors” is preserved literally for reproducibility. Because each rule uses an upper-bound sign, the criteria operate as score ceilings.

### User payload

```json
{
  "source_language": "en",
  "target_language": "<language code>",
  "text": "<English source>",
  "model_output": "<translated candidate>"
}
```

Answer requests additionally contain `context_question` with the English question.

## Limitations

- One LLM judge is not a substitute for bilingual human annotation or inter-annotator agreement.
- The provider-resolved model revision and server configuration are unavailable.
- Temperature zero and a seed do not guarantee deterministic third-party endpoint behavior.
- The score parser historically allowed an integer fallback; `score_origin` makes those cases visible.
- The rubric can apply transliteration expectations unevenly across languages and entity types.
- The sample is balanced but not a census of every translation.
- The V1 source Parquet hashes were not written into the original judge run; the public revision is a retrospective candidate locator and is labeled accordingly.

## License

These annotations derive from CC BY-SA 4.0 HotpotQA/XHotpotQA content and are released under **CC BY-SA 4.0**. The accompanying builder software is MIT-licensed.

## Release family

Browse V1.1, V2 RC1, and both independent GLM-5.2 audit snapshots in the
[XHotpotQA cross-lingual multi-hop QA collection](https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a).

## Resources

- Frozen judge snapshot: https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V1/tree/ba891ae62ed989606c9fc2fd5f08f9e88ef37547
- Pinned XHotpotQA V1.1 source: https://huggingface.co/datasets/Iman998/XhotpotQA/tree/1d29e7918cf1acc045726c70fddba82371833090
- Code: https://github.com/Iman998/XhotpotQA
- Official GLM-5.2 announcement: https://z.ai/blog/glm-5.2
- Official GLM-5.2 model card: https://huggingface.co/zai-org/GLM-5.2
- Paper/archive: forthcoming

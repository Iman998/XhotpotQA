---
pretty_name: XHotpotQA V2 Audited RC1
license: cc-by-sa-4.0
task_categories:
  - question-answering
language:
  - ar
  - bn
  - de
  - el
  - en
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
  - cross-lingual
  - multilingual
  - multi-hop-qa
  - mixed-language-evidence
  - hotpotqa
  - gemma-4
  - audited
size_categories:
  - 10K<n<100K
configs:
  - config_name: xhotpotqa_v2_audited_rc1
    data_files:
      - split: train
        path: data/train-*.parquet
      - split: validation
        path: data/validation-*.parquet
---

<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;border:1px solid #64748b;border-radius:16px;overflow:hidden;margin:0 0 24px;box-shadow:0 8px 24px rgba(15,23,42,.08);">
  <div style="background:linear-gradient(135deg,#1e1b4b 0%,#7c2d12 58%,#b45309 100%);color:#ffffff;padding:24px;">
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;">
      <h1 style="color:#ffffff;margin:0;border:0;font-size:30px;line-height:1.2;">XHotpotQA V2</h1>
      <span style="background:#fef3c7;color:#78350f;border:1px solid #f59e0b;border-radius:999px;padding:5px 11px;font-size:12px;font-weight:800;letter-spacing:.04em;">AUDITED RC1 · INCOMPLETE</span>
    </div>
    <p style="color:#ffedd5;margin:10px 0 3px;font-size:17px;font-weight:700;">Cross-lingual multi-hop QA over mixed-language evidence</p>
    <p style="color:#e2e8f0;margin:0;font-size:14px;">Gemma 4 31B · source-aligned fields · transparent release gate</p>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;padding:12px 18px;border-bottom:1px solid #64748b;">
    <span style="border:1px solid #d97706;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">STATUS · RC1</span>
    <span style="border:1px solid #2563eb;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">ROWS · 22,836</span>
    <span style="border:1px solid #7c3aed;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">GENERATOR · Gemma 4 31B</span>
    <span style="border:1px solid #dc2626;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">MISSING · 230</span>
    <span style="border:1px solid #16a34a;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">LICENSE · CC BY-SA 4.0</span>
  </div>
  <div style="padding:14px 18px;line-height:1.8;">
    <strong>Navigate:</strong>
    <a href="#dataset-at-a-glance">Overview</a> ·
    <a href="#coverage">Coverage</a> ·
    <a href="#quickstart">Load</a> ·
    <a href="#record-structure">Schema</a> ·
    <a href="#methodology-and-generation-provenance">Methodology</a> ·
    <a href="#quality-audit">Quality</a> ·
    <a href="#citation">Citation</a> ·
    <a href="https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a">Collection</a>
  </div>
</div>

<div style="border-left:5px solid #d97706;border-radius:0 10px 10px 0;padding:13px 16px;margin:18px 0;">
  <strong>RC1 release warning.</strong> This is a transparent release candidate, not the corrected canonical V2. The locked files contain 22,836 of 23,066 expected HotpotQA sources. No missing row is generated, copied, or silently hidden by the release builder.
</div>

## Dataset at a glance

XHotpotQA V2 is a translation-derived benchmark for controlled cross-lingual multi-hop QA. A question and answer use one assigned language while candidate paragraphs may use different languages inside the same instance. Stable paragraph and sentence identifiers preserve the HotpotQA supporting chain.

RC1 adds the English source material needed for direct auditing:

- `source_question` and `source_answer` on every released row;
- `source_title` and `source_sentences` for every candidate paragraph;
- row-level structural and quality flags;
- source, input, and release checksums;
- a complete manifest for every expected-but-absent source.

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 18px;">
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">RELEASED</strong>
    <span style="font-size:24px;font-weight:800;">22,836</span><br><small>audited RC1 rows</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">EXPECTED</strong>
    <span style="font-size:24px;font-weight:800;">23,066</span><br><small>HotpotQA sources</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #fca5a5;border-radius:10px;border-top:4px solid #dc2626;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">MISSING</strong>
    <span style="font-size:24px;font-weight:800;">230</span><br><small>explicitly manifested</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #fcd34d;border-radius:10px;border-top:4px solid #d97706;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">COVERAGE</strong>
    <span style="font-size:24px;font-weight:800;">99.003%</span><br><small>not canonical-complete</small>
  </div>
</div>

## Coverage

| Split | Released | Expected | Missing | Coverage |
|---|---:|---:|---:|---:|
| train (HotpotQA hard) | 15,433 | 15,661 | 228 | 98.544% |
| validation (distractor) | 7,403 | 7,405 | 2 | 99.973% |
| **total** | **22,836** | **23,066** | **230** | **99.003%** |

Both missing validation sources are inherited HotpotQA anomalies: one contains a blank sentence inside a supplied distractor paragraph, and one contains supporting-fact index 902 outside the annotated paragraph. Across both splits, 50 missing rows are triggered by a blank source sentence or an out-of-bounds source support annotation; the other 180 are clean-source training omissions from the incomplete generation run. `MISSING_SOURCE_MANIFEST.json` contains the exact absent source IDs. The 50/180 attribution reported here was recomputed by joining those IDs to the official HotpotQA rows and revalidating their sentence arrays and supporting-fact indices; the original run ledger did not encode every retrospective reason class.

## Quickstart

```python
from datasets import load_dataset

DATA_REVISION = "b05ba394ad7312e85625624c90d10258cbab31af"

dataset = load_dataset(
    "Iman998/XhotpotQA-V2",
    "xhotpotqa_v2_audited_rc1",
    revision=DATA_REVISION,
)

row = dataset["validation"][0]
print(row["question"], row["question_language"])
print(row["source_question"])

for paragraph in row["candidates"]:
    print(paragraph["language"], paragraph["source_title"])
    print(paragraph["source_sentences"][0])
    print(paragraph["sentences"][0])
```

The example pins the published RC1 snapshot
[`b05ba394ad7312e85625624c90d10258cbab31af`](https://huggingface.co/datasets/Iman998/XhotpotQA-V2/tree/b05ba394ad7312e85625624c90d10258cbab31af).
Record this revision together with the release-manifest fingerprint in every
experiment instead of loading a moving `main` branch.

## Record structure

| Field | Meaning |
|---|---|
| `id` | Generated XHotpotQA instance identifier |
| `source_id`, `source_split`, `source_position` | Stable location in the pinned HotpotQA source |
| `question`, `answer` | Translated QA pair |
| `question_language`, `answer_language` | ISO-like language codes used by the release |
| `source_question`, `source_answer` | Original English HotpotQA text |
| `candidates` | Ordered translated paragraphs plus original titles and sentences |
| `supporting_facts` | Stable paragraph/sentence links with source titles and bounds checks |
| `status` | `accepted`, `review_required`, or `quarantined` |
| `structural_flags` | Deterministic structural/source-alignment findings |
| `quality_flags` | Deterministic review signals such as source-copy output |
| `source_record_sha256` | Checksum of the canonical source record |
| `input_record_checksum_sha256` | Generator-provided semantic checksum |
| `release_record_sha256` | Checksum of the normalized public row |

### Candidate structure

Each candidate contains:

```text
paragraph_id, candidate_index,
source_title, source_sentences,
title, sentences,
language, language_name,
source_match
```

The release builder takes `source_title` and `source_sentences` from the pinned HotpotQA source. It separately verifies the values recorded by generation and sets `source_match`; a mismatch is never silently accepted.

### Shape-only record preview

Angle-bracketed values below describe the published structure; they are not a
substitute for loading a released row.

```json
{
  "id": "<generated instance identifier>",
  "source_id": "<HotpotQA source identifier>",
  "question": "<translated question>",
  "answer": "<translated answer>",
  "question_language": "<assigned language code>",
  "source_question": "<original English question>",
  "candidates": [
    {
      "paragraph_id": "p00",
      "source_title": "<English source title>",
      "source_sentences": ["<English source sentence>"],
      "sentences": ["<translated sentence>"],
      "language": "<assigned language code>"
    }
  ],
  "supporting_facts": ["<stable paragraph/sentence links>"],
  "status": "accepted | review_required | quarantined"
}
```

## Status and quality policy

`accepted` means the row passed the deterministic checks and has no content-level review flag. `review_required` means structure remains usable but an automatic quality signal needs inspection. `quarantined` means at least one structural or source-alignment condition failed.

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px;">
  <div style="flex:1 1 180px;min-width:0;padding:13px;border:1px solid #86efac;border-radius:10px;border-top:4px solid #16a34a;"><strong>ACCEPTED</strong><br><span style="font-size:13px;">No blocking flag and no content-level review flag.</span></div>
  <div style="flex:1 1 180px;min-width:0;padding:13px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;"><strong>REVIEW REQUIRED</strong><br><span style="font-size:13px;">Structurally usable; automatic quality signal requires inspection.</span></div>
  <div style="flex:1 1 180px;min-width:0;padding:13px;border:1px solid #fca5a5;border-radius:10px;border-top:4px solid #dc2626;"><strong>QUARANTINED</strong><br><span style="font-size:13px;">Structural or source-alignment condition failed.</span></div>
</div>

Representative structural flags include:

- `xhotpot:input_checksum_mismatch`
- `xhotpot:candidate_count_mismatch`
- `xhotpot:source_sentences_mismatch`
- `xhotpot:sentence_count_mismatch`
- `xhotpot:support_annotation_mismatch`
- `source:blank_source_sentence`
- `source:support_index_out_of_range`

Representative quality flags include:

- `xhotpot:question_source_copy`
- `xhotpot:answer_source_copy`
- `xhotpot:paragraph_sentence_source_copy`
- `provenance:assignment_manifest_hash_missing`

Flags prefixed with `source:` describe an inherited source condition. Flags prefixed with `xhotpot:` describe a generated-record or transformation condition. This distinction prevents a HotpotQA anomaly from being misreported as a translation failure.

## Methodology and generation provenance

The supplied run identifies the generator as **Gemma 4 31B Instruct**, served through vLLM's OpenAI-compatible API.

| Property | Recorded value |
|---|---|
| Run configuration model | `google/gemma-4-31B-it` |
| Served model ID stored in rows | `gemma-4-31B-it` |
| Operator-recorded revision | `gemma-4-31B-it-vllm-v0.19.1` |
| Prompt version | `xhotpotqa-translation-v2.0` |
| Prompt SHA-256 | `623496d198d7850c244ff4e2303b7ba9b61548499ce10256ae6691a6b58e71f3` |
| Seed | `20260810` |
| Thinking output | disabled in recorded chat-template options |
| Recorded generation interval | 2026-08-12T20:55:00Z to 2026-08-13T21:23:54Z |

The locked rows contain 22,379 records produced at temperature 0.0, 354 retry records at 0.2, and 103 retry records at 0.3. The operator report describes vLLM 0.19.1 with tensor parallelism over two GPUs. No immutable Hub model commit was persisted, so the served revision string is provenance, not a cryptographic checkpoint identity.

<details>
<summary><strong>Literal V2 translation system prompt</strong></summary>

```text
You are the deterministic translation component of a multilingual QA dataset. Preserve named entities, numbers, dates, yes/no polarity, and sentence boundaries. Do not answer the question and do not add explanations. The user request contains a response_schema; return exactly one valid JSON object that satisfies it, with no additional keys and no Markdown.
```

Single strings must return exactly one `translation` string. Paragraph requests must return exactly one `translations` array with the same cardinality as the source sentence array.

</details>

## Locked source and release integrity

| Input | SHA-256 |
|---|---|
| HotpotQA train v1.1 | `26650cf50234ef5fb2e664ed70bbecdfd87815e6bffc257e068efea5cf7cd316` |
| HotpotQA distractor validation | `e3da074df24e8369009918aa5cdbdd254dadcde4c63f7569d36afd6f2268caa8` |
| V2 train JSONL | `dd1d5bb5950cfe3ca5d013685f9d6e71d1059bde0e5a316462e26a546d491270` |
| V2 validation JSONL | `86542d9918dab1e0587683b51dfa7091a6e8b77171283c66caca35ed70ac931a` |

The builder writes Parquet into a private staging directory, validates counts and identifiers, hashes every output, and only then atomically installs the completed release directory. Existing output directories are never overwritten.

## Quality audit

A separate GLM-5.2 judge release contains a language-balanced audit of 1,840 paragraph, 460 question, and 460 answer translations. V2 mean scores are 94.468, 96.009, and 94.183, respectively. The V1 and V2 samples are almost entirely different source/language assignments, so this is an independent descriptive audit—not a paired improvement estimate.

See [XHotpotQA-GLM52-Judge-V2](https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V2/tree/0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840) for the sanitized scores, prompt hashes, and limitations.

## Release status

RC1 deliberately fails the canonical-completeness gate:

- 230 expected sources are absent;
- every recorded assignment-manifest hash is empty;
- the historical concurrent `retry_count` field is not a reliable per-record count;
- `structural-passed` in the generator means structural validation only, not semantic adequacy or target-language compliance;
- the historical fallback could retain source English when translation failed.

Use RC1 for auditing, code validation, and explicitly status-aware experiments. Do not describe it as the complete or corrected canonical V2.

## Intended uses

- Mixed-language multi-hop QA research.
- Evidence-language and script-robustness analysis.
- Reader and selector diagnostics with stable supporting facts.
- Translation-quality and provenance research using source-aligned fields.

## Out-of-scope uses

- Treating automatic scores as human ground truth.
- Native-language cultural or information-seeking claims.
- Safety-critical decisions.
- Ignoring row status or the missing-source manifest.

## Limitations

- The content originates from English Wikipedia through HotpotQA; translations do not create native information needs.
- Translation and transliteration quality can differ by language, script, entity type, and answer type.
- Exact source copies can be correct for names or titles, so automatic source-copy flags require contextual review.
- The release is incomplete: clean-source omissions require recovery or regeneration, while source-triggered omissions require an explicit policy for malformed upstream rows.
- The accompanying LLM judge is a single uncalibrated model alias and may apply language-specific transliteration preferences inconsistently.

## License and attribution

HotpotQA is distributed under **CC BY-SA 4.0**. XHotpotQA is a transformed, source-aligned resource and is distributed under the same license. Repository software is licensed separately under MIT.

Please cite HotpotQA and the XHotpotQA paper/repository. A persistent article/archive identifier will be added after deposit.

## Citation

Use the XHotpotQA and HotpotQA BibTeX entries in the
[canonical V1.1 dataset card](https://huggingface.co/datasets/Iman998/XhotpotQA#citation).
In the artifact description, report `Iman998/XhotpotQA-V2`, configuration
`xhotpotqa_v2_audited_rc1`, frozen revision
`b05ba394ad7312e85625624c90d10258cbab31af`, and the incomplete RC1 status.

## Release family

Browse V1.1, V2 RC1, and both independent GLM-5.2 audit snapshots in the
[XHotpotQA cross-lingual multi-hop QA collection](https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a).

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px;">
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #5eead4;border-radius:10px;border-top:4px solid #0f766e;"><strong>V1.1</strong><br><span style="font-size:13px;">Canonical audited data</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #fcd34d;border-radius:10px;border-top:4px solid #d97706;"><strong>V2 RC1</strong><br><span style="font-size:13px;">Current incomplete release</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-V2">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;"><strong>Judge · V1</strong><br><span style="font-size:13px;">Independent GLM-5.2 audit</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V1">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;"><strong>Judge · V2</strong><br><span style="font-size:13px;">Independent GLM-5.2 audit</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V2">Open card →</a></div>
</div>

## Resources

- Frozen dataset snapshot: https://huggingface.co/datasets/Iman998/XhotpotQA-V2/tree/b05ba394ad7312e85625624c90d10258cbab31af
- Code: https://github.com/Iman998/XhotpotQA
- Gemma 4 technical report: https://arxiv.org/abs/2607.02770
- vLLM Gemma 4 guide: https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html
- Paper/archive: forthcoming

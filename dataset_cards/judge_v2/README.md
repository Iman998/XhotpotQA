---
pretty_name: XHotpotQA GLM-5.2 Translation Judge — V2
license: cc-by-sa-4.0
arxiv: "2608.27481"
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
  - gemma-4
  - audited
size_categories:
  - 1K<n<10K
configs:
  - config_name: xhotpotqa_glm52_judge_v2
    data_files:
      - split: audit
        path: data/audit-*.parquet
---

<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;border:1px solid #64748b;border-radius:16px;overflow:hidden;margin:0 0 24px;box-shadow:0 8px 24px rgba(15,23,42,.08);">
  <div style="background:linear-gradient(135deg,#0f172a 0%,#155e75 52%,#6d28d9 100%);color:#ffffff;padding:24px;">
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;">
      <h1 style="color:#ffffff;margin:0;border:0;font-size:30px;line-height:1.2;">XHotpotQA · GLM-5.2 Judge</h1>
      <span style="background:#ccfbf1;color:#134e4a;border:1px solid #2dd4bf;border-radius:999px;padding:5px 11px;font-size:12px;font-weight:800;letter-spacing:.04em;">AUDIT SNAPSHOT · V2</span>
    </div>
    <p style="color:#ddd6fe;margin:10px 0 3px;font-size:17px;font-weight:700;">Sanitized audit of the Gemma 4 31B-generated release candidate</p>
    <p style="color:#e2e8f0;margin:0;font-size:14px;">Clean 2,760-unit set · malformed partial-answer run excluded</p>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;padding:12px 18px;border-bottom:1px solid #64748b;">
    <span style="border:1px solid #7c3aed;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">AUDIT · V2 RC1</span>
    <span style="border:1px solid #2563eb;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">ROWS · 2,760</span>
    <span style="border:1px solid #0f766e;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">SCORED · 100%</span>
    <span style="border:1px solid #d97706;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">MODEL · requested alias only</span>
    <span style="border:1px solid #dc2626;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">EXCLUDED · 240 malformed rows</span>
    <span style="border:1px solid #db2777;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">COMPARISON · independent / unpaired</span>
  </div>
  <div style="padding:14px 18px;line-height:1.8;">
    <strong>Navigate:</strong>
    <a href="#dataset-at-a-glance">Overview</a> ·
    <a href="#quickstart">Load</a> ·
    <a href="#methodology-and-sampling-design">Methodology</a> ·
    <a href="#artifact-recovery">Recovery</a> ·
    <a href="#results">Results</a> ·
    <a href="#public-schema">Schema</a> ·
    <a href="#limitations">Limitations</a> ·
    <a href="#citation">Citation</a> ·
    <a href="https://arxiv.org/abs/2608.27481">Paper</a> ·
    <a href="https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a">Collection</a>
  </div>
</div>

<div style="border-left:5px solid #d97706;border-radius:0 10px 10px 0;padding:13px 16px;margin:18px 0;">
  <strong>Quality-label and comparison boundary.</strong> This is an audit of V2 RC1, not a human-certified quality label. The requested API model string was <code>glm-5.2</code>; the provider-resolved checkpoint revision was not stored. V1 and V2 audit samples are independent and must not be described as paired.
</div>

## Dataset at a glance

This release provides the clean final 2,760-row translation audit for XHotpotQA V2 RC1. Paragraphs, questions, and short answers are scored against their English source on a 0–100 scale.

The release builder reconstructs the valid final set from locked artifacts, excludes the known malformed partial answer run, removes hidden reasoning and raw text, and records a cryptographic locator for every source/candidate pair.

The public annotation payload is frozen at Hub revision
[`0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840`](https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V2/tree/0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840).

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 18px;">
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">AUDIT UNITS</strong>
    <span style="font-size:24px;font-weight:800;">2,760</span><br><small>clean final set</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #5eead4;border-radius:10px;border-top:4px solid #0f766e;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">TARGET LANGUAGES</strong>
    <span style="font-size:24px;font-weight:800;">23</span><br><small>balanced sampling</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #fca5a5;border-radius:10px;border-top:4px solid #dc2626;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">EXCLUDED</strong>
    <span style="font-size:24px;font-weight:800;">240</span><br><small>malformed partial-answer rows</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">WEIGHTED MEAN</strong>
    <span style="font-size:24px;font-weight:800;">94.677</span><br><small>0–100 judge scale</small>
  </div>
</div>

## Quickstart

```python
from datasets import load_dataset

AUDIT_REVISION = "0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840"

audit = load_dataset(
    "Iman998/XhotpotQA-GLM52-Judge-V2",
    "xhotpotqa_glm52_judge_v2",
    split="audit",
    revision=AUDIT_REVISION,
)

print(audit.num_rows)  # 2760

thai_answers = audit.filter(lambda row: row["target_language"] == "th" and row["unit"] == "answer")
print(thai_answers["score"])
```

Join against the pinned
[XHotpotQA V2 RC1 snapshot](https://huggingface.co/datasets/Iman998/XhotpotQA-V2/tree/b05ba394ad7312e85625624c90d10258cbab31af)
using `instance_id`, `unit`, and `paragraph_id`. Validate the joined strings with
their exact SHA-256 fields.

## Methodology and sampling design

| Unit | Per language | Total |
|---|---:|---:|
| paragraph | 80 | 1,840 |
| question | 20 | 460 |
| answer | 20 | 460 |
| **all units** | **120** | **2,760** |

- Target languages: 23
- Sampling seed: `20260810`
- Train-derived units: 1,883
- Validation-derived units: 877
- Successfully scored: 2,760
- Failed final rows: 0

## Artifact recovery

The raw `judge_all.records.jsonl` is not a publication artifact. It contains:

- the valid 1,840 paragraph rows;
- the valid 460 question rows;
- 239 scored partial answer rows produced by an incorrect source-unit path, plus one failed row from the same partial run.

The 239 scored rows compare translated answers against the English question instead of the English answer and have a misleading mean of 4.736; the remaining row has no score because its request failed. The clean release discards all 240 rows and uses the dedicated 460-row answer artifact produced with the English answer plus question context.

During paragraph/question evaluation, 276 transient API failures remained after the first attempt sequence. The retry run rescored all 276 successfully. Final paragraph and question coverage is therefore complete.

## Results

| Unit | Count | Mean | Median | SD | Below 60 | Below 80 | At least 90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| paragraph | 1,840 | 94.468 | 96 | 7.53 | 14 | 64 | 1,679 |
| question | 460 | 96.009 | 98 | 8.12 | 6 | 19 | 421 |
| answer | 460 | 94.183 | 100 | 19.46 | 29 | 31 | 419 |
| **weighted overall** | **2,760** | **94.677** | — | — | — | — | — |

Paragraph and question distributions are concentrated near the top of the rubric. Answers have a high median but a wider lower tail, so the answer mean should not be summarized as uniformly high quality across languages.

### Per-language means

| Language | Paragraph | Question | Answer | Overall |
|---|---:|---:|---:|---:|
| Arabic | 95.03 | 97.45 | 96.75 | 95.72 |
| Bengali | 95.15 | 95.15 | 95.40 | 95.19 |
| German | 95.61 | 98.30 | 99.75 | 96.75 |
| Greek | 84.72 | 89.60 | 86.60 | 85.85 |
| Spanish | 95.42 | 95.30 | 94.10 | 95.18 |
| Persian | 94.29 | 94.95 | 91.75 | 93.97 |
| French | 96.51 | 96.90 | 100.00 | 97.16 |
| Hindi | 93.95 | 97.00 | 99.25 | 95.34 |
| Indonesian | 96.51 | 97.40 | 98.50 | 96.99 |
| Italian | 95.89 | 95.70 | 96.75 | 96.00 |
| Japanese | 95.36 | 94.80 | 99.75 | 96.00 |
| Korean | 96.33 | 97.15 | 99.25 | 96.95 |
| Dutch | 94.14 | 96.45 | 92.50 | 94.25 |
| Polish | 94.58 | 99.20 | 98.50 | 96.00 |
| Portuguese | 96.25 | 97.45 | 90.50 | 95.49 |
| Russian | 93.85 | 96.35 | 100.00 | 95.29 |
| Swedish | 92.65 | 96.50 | 98.40 | 94.25 |
| Swahili | 93.34 | 92.60 | 94.65 | 93.43 |
| Thai | 94.47 | 96.35 | 65.30 | 89.92 |
| Turkish | 94.15 | 98.25 | 98.15 | 95.50 |
| Urdu | 93.33 | 95.80 | 90.10 | 93.20 |
| Vietnamese | 96.54 | 95.75 | 95.10 | 96.17 |
| Mandarin Chinese | 94.70 | 93.80 | 85.15 | 92.96 |

Machine-readable full-precision values are in `tables/SUMMARY.json` and `tables/BY_LANGUAGE.csv`. Confidence intervals are in `tables/BOOTSTRAP.json`.

## Interpreting the language tails

The visible judge explanations support three restrained observations:

- Several low Greek paragraph scores identify mixed-script intrusions, untranslated fragments, or meaning reversals.
- Thai answer scores are strongly affected by unchanged Latin-script names and the judge's expectation of Thai transliteration.
- Some Chinese answer penalties similarly concern conventional entity or title rendering.

V2 contains 179 exact English-source copies among the 460 sampled answers. Many are legitimate proper names; others can reflect the historical source-copy fallback. An exact copy is therefore a review signal, not automatically an error. The judge itself may apply transliteration conventions inconsistently.

## Descriptive V1 comparison

| Unit | V1 mean | V2 mean | V2 minus V1 |
|---|---:|---:|---:|
| paragraph | 90.913 | 94.468 | +3.555 |
| question | 93.459 | 96.009 | +2.550 |
| answer | 95.474 | 94.183 | −1.291 |
| weighted overall | 92.097 | 94.677 | +2.580 |

This comparison is not paired. Overlap on source ID, target language, and unit is only nine paragraph units, zero questions, and one answer. The values describe two balanced samples; they do not identify a causal Gemma 4 improvement. The answer audit in particular does not improve uniformly.

## Public schema

| Field | Description |
|---|---|
| `judge_record_id` | Deterministic hash of version and unit identity |
| `dataset_version`, `dataset_revision` | V2 RC1 and locked-input fingerprint |
| `instance_id`, `source_id`, `source_split` | Stable source locators |
| `target_language`, `unit`, `paragraph_id` | Audit identity and stratum |
| `score`, `score_origin` | Integer rating and parser provenance |
| `judge_explanation` | Visible explanation only |
| `source_text_sha256`, `candidate_text_sha256` | Exact text-join verification |
| `requested_judge_model` | Requested API string `glm-5.2` |
| `resolved_judge_revision` | Null; not persisted by the endpoint run |
| `judge_prompt_version`, `judge_prompt_sha256` | Exact historical scoring contract |
| `run_group` | Paragraph/question recovery or dedicated answer run |
| `raw_artifact_sha256`, `raw_line_number` | Private-archive lineage |

The dataset omits source/candidate text duplication, hidden reasoning, raw endpoint details, errors, credentials, and logs.

### Shape-only annotation preview

Angle-bracketed values show the joinable public structure without reproducing
source or candidate text.

```json
{
  "judge_record_id": "<deterministic record hash>",
  "dataset_version": "v2",
  "instance_id": "<XHotpotQA instance identifier>",
  "target_language": "<language code>",
  "unit": "paragraph | question | answer",
  "paragraph_id": "<paragraph identifier or null>",
  "score": 0,
  "score_origin": "<parser provenance>",
  "judge_explanation": "<visible explanation if returned>",
  "source_text_sha256": "<SHA-256>",
  "candidate_text_sha256": "<SHA-256>",
  "requested_judge_model": "glm-5.2",
  "resolved_judge_revision": null,
  "run_group": "<recovery or dedicated answer run>"
}
```

## Score provenance

| Origin | Rows |
|---|---:|
| visible explicit `SCORE:` line | 2,756 |
| last-integer reasoning fallback | 4 |

The four reasoning-fallback rows have no visible explanation. Their origin is retained, but the reasoning text is not released.

## Model provenance

| Setting | Value |
|---|---|
| Requested judge model | `glm-5.2` |
| Provider-resolved revision | not recorded |
| Temperature | 0.0 |
| Seed | `20260810` |
| Maximum output tokens | 4,000 |
| Concurrent workers | 1 |

The official GLM-5.2 sources establish the public model family, not the identity behind a third-party alias. This release therefore makes no immutable-checkpoint claim.

## Historical prompt contract

The artifacts contain one source-referenced score. They do not contain a second reference-free score.

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

The historical phrase “critical error floors” is reproduced exactly. Because the rules specify upper bounds, they function as score ceilings.

### User payload

```json
{
  "source_language": "en",
  "target_language": "<language code>",
  "text": "<English source>",
  "model_output": "<translated candidate>"
}
```

The answer request additionally carries the original English question as `context_question`.

## Limitations

- Scores come from one uncalibrated LLM judge rather than bilingual human annotators.
- The provider-resolved judge model and server revision are unknown.
- The V1/V2 samples are almost entirely unpaired.
- Language-specific entity and transliteration preferences can affect scores.
- High medians coexist with meaningful lower-tail failures.
- The audit covers a balanced sample, not all 22,836 RC1 rows.
- The underlying V2 dataset remains incomplete and status-bearing.

## License

These annotations derive from CC BY-SA 4.0 HotpotQA/XHotpotQA content and are released under **CC BY-SA 4.0**. Builder code is MIT-licensed.

## Citation

Use the XHotpotQA and HotpotQA BibTeX entries in the
[canonical V1.1 dataset card](https://huggingface.co/datasets/Iman998/XhotpotQA#citation).
The XHotpotQA paper is archived as
[arXiv:2608.27481](https://arxiv.org/abs/2608.27481), DOI
[`10.48550/arXiv.2608.27481`](https://doi.org/10.48550/arXiv.2608.27481).
In the audit-artifact description, report
`Iman998/XhotpotQA-GLM52-Judge-V2`, configuration
`xhotpotqa_glm52_judge_v2`, frozen revision
`0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840`, the requested `glm-5.2` alias,
the independent/unpaired sampling design, and the exclusion of the 240
malformed partial-answer rows.

## Release family

Browse V1.1, V2 RC1, and both independent GLM-5.2 audit snapshots in the
[XHotpotQA cross-lingual multi-hop QA collection](https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a).

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px;">
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #5eead4;border-radius:10px;border-top:4px solid #0f766e;"><strong>V1.1</strong><br><span style="font-size:13px;">Canonical audited data</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #fcd34d;border-radius:10px;border-top:4px solid #d97706;"><strong>V2 RC1</strong><br><span style="font-size:13px;">Incomplete source dataset</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-V2">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;"><strong>Judge · V1</strong><br><span style="font-size:13px;">Independent comparison audit</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V1">Open card →</a></div>
  <div style="flex:1 1 155px;min-width:0;padding:12px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;"><strong>Judge · V2</strong><br><span style="font-size:13px;">Current independent audit</span><br><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V2">Open card →</a></div>
</div>

## Resources

- Frozen judge snapshot: https://huggingface.co/datasets/Iman998/XhotpotQA-GLM52-Judge-V2/tree/0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840
- Pinned V2 RC1 source: https://huggingface.co/datasets/Iman998/XhotpotQA-V2/tree/b05ba394ad7312e85625624c90d10258cbab31af
- Code: https://github.com/Iman998/XhotpotQA
- Paper: https://arxiv.org/abs/2608.27481
- Paper DOI: https://doi.org/10.48550/arXiv.2608.27481
- Official GLM-5.2 announcement: https://z.ai/blog/glm-5.2
- Official GLM-5.2 model card: https://huggingface.co/zai-org/GLM-5.2
- Gemma 4 technical report: https://arxiv.org/abs/2607.02770

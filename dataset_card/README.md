---
pretty_name: XHotpotQA
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
license: cc-by-sa-4.0
annotations_creators:
- crowdsourced
- machine-generated
language_creators:
- found
- machine-generated
multilinguality:
- multilingual
source_datasets:
- extended
task_categories:
- question-answering
tags:
- cross-lingual
- multi-hop-question-answering
- mixed-language-evidence
- supporting-fact-identification
- evidence-selection
- synthetic-translation
- parquet
size_categories:
- 10K<n<100K
configs:
- config_name: xhotpotqa_v1_1_audited
  default: true
  data_files:
  - split: train
    path: data/xhotpotqa_v1_1_audited/train-*.parquet
  - split: validation
    path: data/xhotpotqa_v1_1_audited/validation-*.parquet
- config_name: xhotpotqa_v1_audited
  data_files:
  - split: train
    path: data/xhotpotqa_v1_audited/train-*.parquet
  - split: validation
    path: data/xhotpotqa_v1_audited/validation-*.parquet
---

<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;border:1px solid #64748b;border-radius:16px;overflow:hidden;margin:0 0 24px;box-shadow:0 8px 24px rgba(15,23,42,.08);">
  <div style="background:linear-gradient(135deg,#0f172a 0%,#164e63 55%,#0f766e 100%);color:#ffffff;padding:24px;">
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;">
      <h1 style="color:#ffffff;margin:0;border:0;font-size:30px;line-height:1.2;">XHotpotQA</h1>
      <span style="background:#dcfce7;color:#14532d;border:1px solid #22c55e;border-radius:999px;padding:5px 11px;font-size:12px;font-weight:800;letter-spacing:.04em;">AUDITED V1.1 · PUBLIC</span>
    </div>
    <p style="color:#ccfbf1;margin:10px 0 3px;font-size:17px;font-weight:700;">Cross-lingual multi-hop question answering over mixed-language evidence</p>
    <p style="color:#e2e8f0;margin:0;font-size:14px;">One question · multiple evidence paragraphs · languages may change between hops</p>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;padding:12px 18px;border-bottom:1px solid #64748b;">
    <span style="border:1px solid #2563eb;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">23,066 released rows</span>
    <span style="border:1px solid #0f766e;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">Supplied-candidate MHQA</span>
    <span style="border:1px solid #7c3aed;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">Parquet · 22 fields</span>
    <span style="border:1px solid #16a34a;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">CC BY-SA 4.0</span>
  </div>
  <div style="padding:14px 18px;line-height:1.8;">
    <strong>Navigate:</strong>
    <a href="#dataset-at-a-glance">Overview</a> ·
    <a href="#load-in-30-seconds">Load</a> ·
    <a href="#data-format">Structure</a> ·
    <a href="#quality-and-version-policy">Quality</a> ·
    <a href="#artifact-verified-validation-analysis">Findings</a> ·
    <a href="#citation">Citation</a> ·
    <a href="https://github.com/Iman998/XhotpotQA/tree/v0.4.1">Code v0.4.1</a>
  </div>
</div>

XHotpotQA is a controlled benchmark for studying whether a system can select and
compose evidence when the question, gold paragraphs, and distractors are not
necessarily written in the same language. It adapts the supplied-candidate
[HotpotQA distractor task](https://huggingface.co/datasets/hotpotqa/hotpot_qa)
to 24 languages. It preserves recovered paragraph order, sentence arrays, task
metadata, answers, and support annotations while explicitly flagging structural
deviations from the source.

The preferred public configuration is **`xhotpotqa_v1_1_audited`**. It keeps
the audit-preserving V1 translations and adds every original English candidate
paragraph as `source_sentences`, making paragraph-level inspection possible
without a positional join to a separate HotpotQA file. The frozen
`xhotpotqa_v1_audited` configuration remains available unchanged for exact
reproduction of earlier experiments. Neither configuration is the corrected
canonical V2. Every
eligible source item in the released scope is retained, including rows with
known structural defects, and every row carries machine-readable `status` and
`structural_flags` fields. The frozen
V1.1 data snapshot is Hub revision
[`1d29e7918cf1acc045726c70fddba82371833090`](https://huggingface.co/datasets/Iman998/XhotpotQA/tree/1d29e7918cf1acc045726c70fddba82371833090).

<div style="border-left:5px solid #d97706;border-radius:0 10px 10px 0;padding:13px 16px;margin:18px 0;">
  <strong>Release status · recovered and audited, not corrected V2.</strong><br>
  This page serves a transparent, artifact-verified V1 recovery. Amber denotes
  incomplete historical provenance; “prospective” means that an artifact is not
  included. Neither label means that corrected V2 data have already been generated.
</div>

## Dataset at a glance

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 18px;">
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">TRAIN</strong>
    <span style="font-size:24px;font-weight:800;">15,661</span><br><small>hard-source rows</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">VALIDATION</strong>
    <span style="font-size:24px;font-weight:800;">7,405</span><br><small>full distractor validation</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #5eead4;border-radius:10px;border-top:4px solid #0f766e;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">TOTAL</strong>
    <span style="font-size:24px;font-weight:800;">23,066</span><br><small>one view per source</small>
  </div>
  <div style="flex:1 1 145px;min-width:0;padding:13px;border:1px solid #f9a8d4;border-radius:10px;border-top:4px solid #db2777;">
    <strong style="display:block;font-size:12px;letter-spacing:.05em;">LANGUAGE SPACE</strong>
    <span style="font-size:24px;font-weight:800;">24</span><br><small>ISO 639-1 assignments</small>
  </div>
</div>

| Property | Value |
|---|---|
| Task | Supplied-candidate cross-lingual multi-hop QA |
| Source | [HotpotQA distractor](https://huggingface.co/datasets/hotpotqa/hotpot_qa); hard-only train and full distractor validation |
| Evidence | Ordered candidate paragraphs with recovered sentence arrays |
| Supervision | Answer plus sentence-level supporting facts |
| Preferred configuration | `xhotpotqa_v1_1_audited` (default; adds original English `source_sentences`) |
| Frozen legacy configuration | `xhotpotqa_v1_audited` at revision `52b8bee…` |
| Storage | Sharded, Zstandard-compressed Parquet |
| Released rows | 23,066 |
| Unit of release | One recovered view per HotpotQA source |

### One item, several language roles

Each item keeps the supplied HotpotQA candidate set while independently exposing
the language assignments of the question, the two gold paragraphs, and every
distractor. The colors below identify **roles**, not quality grades.

<div style="display:flex;flex-wrap:wrap;gap:9px;margin:12px 0 16px;">
  <div style="flex:1 1 140px;min-width:0;padding:12px;border:1px solid #c4b5fd;border-radius:10px;border-top:4px solid #7c3aed;"><strong>Question</strong><br><span style="font-size:13px;">assigned language <code>L_q</code></span></div>
  <div style="flex:1 1 140px;min-width:0;padding:12px;border:1px solid #93c5fd;border-radius:10px;border-top:4px solid #2563eb;"><strong>Gold A</strong><br><span style="font-size:13px;">evidence language <code>L_g1</code></span></div>
  <div style="flex:1 1 140px;min-width:0;padding:12px;border:1px solid #86efac;border-radius:10px;border-top:4px solid #16a34a;"><strong>Gold B</strong><br><span style="font-size:13px;">evidence language <code>L_g2</code></span></div>
  <div style="flex:1 1 140px;min-width:0;padding:12px;border:1px solid #cbd5e1;border-radius:10px;border-top:4px solid #64748b;"><strong>Distractor <code>j</code></strong><br><span style="font-size:13px;">assigned language <code>L_dj</code></span></div>
  <div style="flex:1 1 140px;min-width:0;padding:12px;border:1px solid #f9a8d4;border-radius:10px;border-top:4px solid #db2777;"><strong>Gold answer</strong><br><span style="font-size:13px;"><code>L_y = L_q</code></span></div>
</div>

**Example from the released validation split:** a Swahili question and stored
answer are paired with supporting and distractor paragraphs assigned to other
languages. The task is to connect the annotated evidence and return the answer
in Swahili; the full record preview appears under [Data format](#data-format).

The benchmark therefore measures supplied-candidate evidence selection and answer
composition under language mismatch. It does not claim to measure open-corpus
retrieval or naturally occurring multilingual search behavior.

## Release status

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px;">
  <div style="flex:1 1 190px;min-width:0;padding:14px;border:1px solid #86efac;border-radius:10px;border-top:5px solid #16a34a;">
    <strong>AVAILABLE · AUDITED V1.1</strong><br>
    <span style="font-size:13px;">15,661 train and 7,405 validation rows, now with original English paragraph sentences.</span>
  </div>
  <div style="flex:1 1 190px;min-width:0;padding:14px;border:1px solid #cbd5e1;border-radius:10px;border-top:5px solid #64748b;">
    <strong>NOT PUBLISHED · XHotpotQA+</strong><br>
    <span style="font-size:13px;">The complete parallel validation mapping is unavailable; no Hub config is claimed.</span>
  </div>
  <div style="flex:1 1 190px;min-width:0;padding:14px;border:1px solid #fcd34d;border-radius:10px;border-top:5px solid #d97706;">
    <strong>PUBLIC RC1 · NOT CANONICAL V2</strong><br>
    <span style="font-size:13px;"><a href="https://huggingface.co/datasets/Iman998/XhotpotQA-V2/tree/b05ba394ad7312e85625624c90d10258cbab31af">V2 RC1</a> covers 22,836/23,066 intended rows and remains incomplete.</span>
  </div>
</div>

> **Important:** `status="quarantined"` is a data-quality label, not an
> exclusion. Quarantined rows remain in the released splits so that counts,
> source alignment, and reported analyses are reproducible. Users must state
> whether they evaluate the complete split or a status-filtered subset.

### Release-gate contract

<details>
<summary><b>Why audited V1 publication does not satisfy the corrected V2 gate</b></summary>

| Gate | Audited V1 in this payload | Prospective corrected V2 |
|---|---|---|
| Required rows available | ✅ Complete | ⚠️ RC1 is 230 rows short |
| Structural status retained | ✅ Per row | Required before release |
| File hashes and counts frozen | ✅ `RELEASE_MANIFEST.json` | Required before release |
| Paired V1–V2 quality evidence | Not applicable to publishing recovered V1 | ⛔ Independent GLM audits are not paired evidence |
| Safe claim | Transparent, audit-preserving recovered resource | Pipeline plan only |

The V1 release gate is **transparency**, not a claim that every translation is
correct. A future corrected V2 has a stricter gate: completed artifacts,
structural validation, and paired quality evidence.

</details>

## Why XHotpotQA?

A conventional multilingual QA example often keeps the question and its evidence
in one language. XHotpotQA instead creates **within-instance mixing**:

- the question and answer share one assigned language;
- each candidate paragraph has its own assigned language;
- the two gold paragraphs can be aligned with the question, partially mismatched,
  or fully mismatched in one or multiple languages; and
- multilingual distractors remain visible to evidence-selection systems.

A bridge question can therefore require reading one fact in one language,
following the bridge in another, rejecting distractors in several more, and
returning the answer in the question language. Because the candidate set is
supplied, XHotpotQA isolates evidence selection and composition; it is **not** an
open-Wikipedia retrieval benchmark.

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px;">
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #93c5fd;border-radius:10px;"><strong>Mixed evidence</strong><br><span style="font-size:13px;">Language varies within an item—not only between dataset examples.</span></div>
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #5eead4;border-radius:10px;"><strong>Role-aware analysis</strong><br><span style="font-size:13px;">Question, gold hops, and distractors remain separately identifiable.</span></div>
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #c4b5fd;border-radius:10px;"><strong>Auditable release</strong><br><span style="font-size:13px;">Every row carries provenance, status, flags, and a record checksum.</span></div>
</div>

## Load in 30 seconds

| If you want to… | Start with | Reporting requirement |
|---|---|---|
| Reproduce the frozen benchmark | Complete `validation` split | Denominator **7,405** |
| Reproduce the reported 439-item exclusion | `status != "quarantined"` | Denominator **6,966**, including four `review_required` rows |
| Run the stricter accepted-only view | `status == "accepted"` | Denominator **6,962**; label it separately |
| Inspect without a full download | `streaming=True` | Pin the revision used |
| Verify release integrity | `RELEASE_MANIFEST.json` | Archive the manifest with predictions |

Install a recent version of `datasets`:

```bash
pip install -U datasets
```

```python
from datasets import load_dataset

DATA_REVISION = "1d29e7918cf1acc045726c70fddba82371833090"

dataset = load_dataset(
    "Iman998/XhotpotQA",
    "xhotpotqa_v1_1_audited",
    revision=DATA_REVISION,
)

print(dataset)
print(len(dataset["train"]))  # 15_661
print(len(dataset["validation"]))  # 7_405

row = dataset["validation"][0]
print(row["question_language"], row["question"])
print(row["status"], row["structural_flags"])
print(row["supporting_facts"])
```

<details>
<summary><b>Advanced loading: streaming and status filters</b></summary>

For low-memory inspection, stream Parquet shards:

```python
from datasets import load_dataset

DATA_REVISION = "1d29e7918cf1acc045726c70fddba82371833090"

stream = load_dataset(
    "Iman998/XhotpotQA",
    "xhotpotqa_v1_1_audited",
    split="validation",
    streaming=True,
    revision=DATA_REVISION,
)

first = next(iter(stream))
print(first["source_id"], first["question_language"])
```

The paper's 439-item structural-gate sensitivity keeps both `accepted` and
`review_required` rows. The stricter accepted-only view removes four additional
non-blocking title-collision cases:

```python
validation = dataset["validation"]
non_quarantined = validation.filter(lambda row: row["status"] != "quarantined")
accepted_only = validation.filter(lambda row: row["status"] == "accepted")

print(len(non_quarantined))  # 6_966: reproduces the reported 439-item exclusion
print(len(accepted_only))  # 6_962: stricter sensitivity view

print(
    {
        status: validation.filter(lambda row: row["status"] == status).num_rows
        for status in ("accepted", "review_required", "quarantined")
    }
)
```

The complete 7,405-row validation split should remain the primary denominator
when reproducing the frozen V1 analyses. Neither filtered view is a replacement
test split, and the two denominators must not be conflated.

</details>

### Record preview

The following is an **abbreviated projection of a real accepted validation
record**. Candidate text is omitted here only to keep the card readable; the
Parquet row contains every translated title, ordered sentence, supporting fact,
provenance field, and checksum described below.

```json
{
  "id": "5a8b57f25542995d1e6f1371",
  "source_split": "validation",
  "question": "Je, Scott Derrickson na Ed Wood walikuwa wa taifa moja?",
  "answer": "ndiyo",
  "question_language": "sw",
  "answer_language": "sw",
  "question_type": "comparison",
  "difficulty": "hard",
  "candidate_preview": [
    {"paragraph_id": "p00", "title": "এড উড (ফিল্ম)", "language_code": "bn"},
    {"paragraph_id": "p01", "title": "Скотт Дерриксон", "language_code": "ru"},
    {"paragraph_id": "p02", "title": "Woodson, Arkansas", "language_code": "vi"}
  ],
  "supporting_facts": [
    {"paragraph_id": "p01", "sentence_index": 0, "in_bounds": true},
    {"paragraph_id": "p04", "sentence_index": 0, "in_bounds": true}
  ],
  "status": "accepted",
  "structural_flags": []
}
```

This preview makes the intended challenge concrete: the Swahili question must
be resolved from evidence assigned to other languages while distractors remain
in the same supplied candidate set. `candidate_preview` is a card-only summary,
not an additional dataset column.

## Data format

| Field family | Core fields | Purpose |
|---|---|---|
| 🔑 Identity | `id`, `source_id`, `source_*_position` | Stable identity and source/release alignment |
| 💬 QA | `question`, `answer`, source text, language fields | Translated task plus original reference text |
| 📚 Evidence | `candidates[]`, `supporting_facts[]` | Ordered paragraphs and sentence-level supervision |
| 🧭 Audit | `status`, `structural_flags[]`, `record_sha256` | Non-destructive quality findings and integrity |
| 🧾 Provenance | `provenance.*` | Traceable source → shard → release build |

All source and release positions are explicit, nested candidates preserve the
recovered sentence arrays, and an audit finding never causes an implicit row
drop.

<details>
<summary><b>Complete 22-field schema, nested fields, and language inventory</b></summary>

### Top-level schema

| Field | Arrow type | Meaning |
|---|---|---|
| `id` | string | Stable released row ID; equal to the HotpotQA source ID in this one-view release |
| `source_id` | string | Stable HotpotQA source ID used for grouping future views |
| `source_split` | string | `train` or `validation` |
| `source_position` | int32 | Position in the original ordered HotpotQA source file |
| `release_position` | int32 | Dense zero-based position within the released split |
| `legacy_view_index` | int16 | Selected index in the recovered legacy view group |
| `question` | string | Translated question |
| `answer` | string | Translated answer |
| `question_language` | string | Assigned ISO 639-1 code, or `und` when unresolved |
| `question_language_name` | string | Assigned question-language name |
| `answer_language` | string | Assigned ISO 639-1 code; equal to `question_language` in V1 |
| `answer_language_name` | string | Assigned answer-language name |
| `source_question` | string | Original HotpotQA question |
| `source_answer` | string | Original HotpotQA answer |
| `question_type` | string | HotpotQA question type |
| `difficulty` | string | HotpotQA difficulty label |
| `candidates` | list[struct] | Ordered translated candidate paragraphs |
| `supporting_facts` | list[struct] | Reattached sentence-level gold evidence |
| `status` | string | `accepted`, `review_required`, or `quarantined` |
| `structural_flags` | list[string] | Audit findings for the row |
| `provenance` | struct | Source, shard, translation, assignment, selection, and builder provenance |
| `record_sha256` | string | SHA-256 of the canonical released record, excluding this field itself |

### Nested fields

```text
candidates: list[
  paragraph_id: string
  candidate_index: int16
  source_title: string
  source_sentences: list[string]
  title: string
  sentences: list[string]
  language: string
  language_code: string
]

supporting_facts: list[
  source_title: string
  paragraph_id: string | null
  candidate_index: int16 | null
  sentence_index: int32
  in_bounds: bool
]

provenance: struct[
  source_dataset: string
  source_file: string
  source_record_sha256: string
  legacy_shard: string
  legacy_shard_row: int32
  legacy_raw_sha256: string
  translation_model: string
  prompt_version: string
  assignment_version: string
  release_selection: string
  build_version: string
]
```

Paragraph IDs are positional (`p00`, `p01`, …) and follow the recovered
candidate order; `candidate_index` preserves the corresponding integer
position. `source_title` and `source_sentences` retain the original English
HotpotQA paragraph, while `title` and `sentences` store its translated form.
Supporting facts are joined through the
source title and then represented by candidate/paragraph ID plus sentence
index. A null `paragraph_id` or `candidate_index`, or
`in_bounds=false`, preserves a failed join or unavailable translated sentence
instead of inventing a repair.

### Language inventory

| Code | Language | Code | Language | Code | Language |
|---|---|---|---|---|---|
| ar | Arabic | bn | Bengali | de | German |
| el | Greek | en | English | es | Spanish |
| fa | Persian | fr | French | hi | Hindi |
| id | Indonesian | it | Italian | ja | Japanese |
| ko | Korean | nl | Dutch | pl | Polish |
| pt | Portuguese | ru | Russian | sv | Swedish |
| sw | Swahili | th | Thai | tr | Turkish |
| ur | Urdu | vi | Vietnamese | zh | Mandarin Chinese |

Language codes follow ISO 639-1. Top-level `question_language` and
`answer_language` contain codes; their `*_language_name` companions contain
names. Candidate structs likewise contain both `language_code` and
`language`. The schema permits `und` for unresolved assignments, but no frozen
question or answer row uses it. The display name “Mandarin Chinese” for `zh`
follows the recovered assignment vocabulary; it is not a language-identification
result. These assignments are not human quality certifications.

</details>

## 🏗️ Construction and provenance

The released configuration is reconstructed from historical translation shards
that used pandas `orient="columns"` JSON and did not carry HotpotQA IDs or
support labels. The release builder performs this audited transformation:

| Step | Operation | Reproducibility artifact |
|---:|---|---|
| **1** | Freeze the official HotpotQA snapshot and recovered V1 shards | Pinned names, sizes, and SHA-256 values |
| **2** | Reattach IDs, task metadata, and support labels by an ordered join | Source positions and source-record hashes |
| **3** | Select one public train view per source | Explicit SHA-256 selection rule |
| **4** | Run a non-destructive structural audit | Per-row status and flags |
| **5** | Package Parquet shards and freeze the release | `RELEASE_MANIFEST.json` |

1. Train sources are the 15,661 `hard` records from HotpotQA train; validation
   uses all 7,405 distractor records.
2. The ordered join reattaches stable source IDs, English source fields,
   question type, difficulty, and supporting facts.
3. Each training source has 24 recovered question–answer views in a fixed
   language order. The public V1 base selects exactly one view per source.
4. Validation has one recovered legacy view per source, so that view is retained.
5. Every row is audited and emitted even when a defect is detected. No translated
   sentence, title, answer, or support index is silently rewritten.
6. Parquet file hashes, row counts, status counts, flag counts, and language
   counts are recorded in `RELEASE_MANIFEST.json`.

<details>
<summary><b>Historical assignment and deterministic public train selection</b></summary>

### Deterministic public train selection

The historical base mapping was random and its seed was not preserved. It cannot
be reproduced exactly from the surviving archive. To make this public one-view
release reproducible, the selected training view is:

$$
v_i =
\operatorname{int}\!\left(
\operatorname{SHA256}
(\texttt{"xhotpotqa-public-v1|"} \Vert \texttt{source\_id}_i)[0{:}8]
\right) \bmod 24.
$$

Here `[0:8]` means the first eight digest bytes interpreted as an unsigned
big-endian integer. This is a **release selection rule**, not a reconstruction of
the lost historical random assignment. The row fields make the distinction
explicit:

| Field | Train value | Validation value |
|---|---|---|
| `provenance.assignment_version` | `legacy-random-v1-unseeded` | `legacy-random-v1-unseeded` |
| `provenance.release_selection` | `sha256-public-v1` | `legacy-validation-view` |
| `legacy_view_index` | 0–23, selected by the rule above | 0, the only recovered view for that source |

### Recovered model provenance

V1 records preserve the historical label
`gpt-4o-mini (historical mutable alias)` in
`provenance.translation_model`. The provider-resolved checkpoint revision was
not stored, so this label must not be interpreted as proof of an exact backend
snapshot. Likewise, `provenance.prompt_version="legacy-v1-recovered"` and
`provenance.assignment_version="legacy-random-v1-unseeded"` document
incomplete historical provenance instead of filling it with guessed values.

The separately published V2 RC1 records identify **Gemma 4 31B Instruct** served
through vLLM's OpenAI-compatible API. That provenance applies only to V2 RC1;
it does not retroactively identify the V1 backend. V2 RC1 is incomplete at
22,836 of 23,066 intended sources and must not be described as canonical V2.

</details>

## Quality and version policy

### What the status field means

| Status | Interpretation |
|---|---|
| `accepted` | No canonical-release-blocking structural flag was found by the automated audit |
| `review_required` | A non-blocking ambiguity requires explicit review |
| `quarantined` | At least one structural defect requiring correction before a canonical release was preserved |

These labels describe **structural validity under the implemented checks**. They
do not certify semantic translation adequacy, fluency, cultural suitability, or
paper acceptance.

<table>
  <tr>
    <th>Split</th>
    <th><img alt="Accepted" src="https://img.shields.io/badge/ACCEPTED-no%20blocking%20flag-16a34a?style=flat-square"></th>
    <th><img alt="Review required" src="https://img.shields.io/badge/REVIEW-ambiguity-2563eb?style=flat-square"></th>
    <th><img alt="Quarantined" src="https://img.shields.io/badge/QUARANTINED-blocking%20flag-dc2626?style=flat-square"></th>
    <th>Total</th>
  </tr>
  <tr>
    <td><b>Train</b></td><td align="right">14,721</td><td align="right">15</td><td align="right">925</td><td align="right"><b>15,661</b></td>
  </tr>
  <tr>
    <td><b>Validation</b></td><td align="right">6,962</td><td align="right">4</td><td align="right">439</td><td align="right"><b>7,405</b></td>
  </tr>
</table>

> **⚠️ Status is not a translation-quality score.** `accepted` means that the row
> passed the implemented structural checks; `quarantined` means that the
> detected structure was preserved for auditability. Neither label replaces
> human semantic evaluation.

The validator checks candidate cardinality and shape, sentence preservation,
blank content, support-title resolution, support-index bounds, normalized title
collisions, and question/answer presence. `structural_flags` stores the exact
findings, including flags such as
`paragraph_sentence_shortfall`,
`paragraph_sentence_surplus`, `blank_sentence`,
`support_index_out_of_range`, and
`duplicate_normalized_translated_title`.

<details>
<summary><b>Detailed train and validation audit counts</b></summary>

### Audited validation findings

The recovered validation audit retains all 7,405 sources:

| Finding | Count | Counting unit |
|---|---:|---|
| Outside the union of canonical-release-blocking flags | **6,966** | source rows |
| In the union of canonical-release-blocking flags | **439** (5.93%) | source rows |
| Sentence-cardinality mismatch | 424 | paragraph events affecting 407 rows |
| At least one blank translated sentence | 33 | source rows |
| Unavailable translated support index | 9 | source rows |
| Duplicate normalized translated title | 4 | source rows |

Component sets overlap and therefore must not be added. The four
duplicate-title rows are non-blocking `review_required` records, so they belong
to the 6,966 rows outside the canonical-release-blocking union rather than to the 439-row
quarantine.

### Audited train findings

The deterministic public projection retains all 15,661 hard training sources:

| Status or row-level flag | Rows |
|---|---:|
| `accepted` | **14,721** |
| `quarantined` | **925** |
| `review_required` | **15** |
| `paragraph_sentence_shortfall` | 853 |
| `paragraph_sentence_surplus` | 8 |
| `blank_sentence` | 68 |
| `support_index_out_of_range` | 24 |
| `duplicate_normalized_translated_title` | 15 |

Flag sets overlap; the status rows form the exhaustive 15,661-row partition.
The authoritative machine-readable counts and file hashes are in
`RELEASE_MANIFEST.json` next to the released Parquet files.

</details>

### Sensitivity to the validation quality gate

Removing the 439 `quarantined` validation items while retaining all 6,966
non-quarantined rows changed every tested aggregate EM/F1
metric by at most **0.51 points** and either primary language-condition contrast
by at most **0.22 points**. All eight item-bootstrap intervals for the
clean-minus-complete contrast shifts included zero. This paired source-item
sensitivity analysis used 2,000 bootstrap replicates. The result indicates that the
reported V1 language-alignment pattern is not concentrated in the flagged
subset; it does **not** make the underlying defects acceptable.

## Task formulation and analysis strata

### Operational task definition

Represent an item as

$$
x = (q, y, C, G, S, \Lambda),
$$

where \\(q\\) is the question, \\(y\\) the gold answer,
\\(C=(p_1,\ldots,p_m)\\) the ordered candidate paragraphs, \\(G\subseteq C\\) the
gold-paragraph set, \\(S\\) the sentence-level supporting facts, and
\\(\Lambda=(L_q,L_y,L_{p_1},\ldots,L_{p_m})\\) the realized language assignment.
For V1, \\(L_y=L_q\\). A reader predicts \\(\hat y\\); a selector predicts
\\(\hat S\\) or \\(\hat G\\); and an end-to-end supplied-candidate system predicts both.

The intended two-hop composition can be written schematically as

$$
\begin{aligned}
z &= f_1(q,e_1), \\
\hat y &= f_2(q,z,e_2),
\qquad e_1,e_2\in S.
\end{aligned}
$$

with evidence units potentially written in different languages. This is an
operational representation of the annotated task, not a guarantee of
counterfactual evidence necessity: HotpotQA artifacts can occasionally permit
single-hop or parametric solutions.

| Symbol | Released representation |
|---|---|
| \\(q,y,L_q,L_y\\) | `question`, `answer`, `question_language`, `answer_language` |
| \\(C,L_{p_i}\\) | ordered `candidates` and each candidate's `language_code` |
| \\(G,S\\) | paragraph-linked and sentence-indexed `supporting_facts` |
| \\(\hat y,\hat S\\) | consumer prediction artifacts; not stored as dataset labels |

Let \\(L_q\\) be the question language, \\(G\\) the gold-paragraph set,
\\(D\\) the distractor set, and \\(L_p\\) the assigned language of paragraph
\\(p\\). XHotpotQA reports:

$$
\begin{aligned}
\rho_G &= \frac{1}{|G|}\sum_{p\in G}\mathbf{1}[L_p \neq L_q], \\
\rho_D &= \frac{1}{|D|}\sum_{p\in D}\mathbf{1}[L_p \neq L_q].
\end{aligned}
$$

When an item has no distractors, \\(\rho_D\\) is not applicable rather than
zero. The analysis also derives normalized gold-evidence language entropy
\\(H_G\\), candidate-language count \\(K_C\\), question-to-gold script
relation, and these realized strata:

| Stratum | Definition | Validation count |
|---|---|---:|
| S0 | Gold and distractors fully aligned with the question | 0 |
| S1 | Gold aligned; multilingual distractors | 14 |
| S2 | Partial gold mismatch, \\(0<\rho_G<1\\) | 564 |
| S3 | Full gold mismatch in one evidence language | 312 |
| S4 | Full gold mismatch across multiple evidence languages | 6,515 |

S1 is too small for inferential comparison, and S0 is unpopulated in this
realized validation assignment.

## Artifact-verified validation analysis

<div style="display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 14px;">
  <span style="border:1px solid #16a34a;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">EVIDENCE · artifact verified</span>
  <span style="border:1px solid #2563eb;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">SCOPE · frozen V1 descriptives</span>
  <span style="border:1px solid #64748b;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;">CAUSAL CLAIM · none</span>
</div>

The following statistics were recomputed from the recovered 7,405-row validation
metadata and surviving prediction artifacts. They are frozen-run descriptive
associations—not a leaderboard and not causal estimates of language effects.

<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 20px;">
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #5eead4;border-radius:10px;border-top:5px solid #0f766e;">
    <strong style="display:block;font-size:12px;">PERVASIVE MIXING</strong>
    <span style="font-size:24px;font-weight:800;">99.811%</span><br><span style="font-size:13px;">question differs from at least one assigned gold-paragraph language</span>
  </div>
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #fca5a5;border-radius:10px;border-top:5px solid #dc2626;">
    <strong style="display:block;font-size:12px;">READER S4 − S2</strong>
    <span style="font-size:22px;font-weight:800;">−10.25 to −15.79</span><br><span style="font-size:13px;">answer-F1 points across three surviving artifacts</span>
  </div>
  <div style="flex:1 1 180px;min-width:0;padding:14px;border:1px solid #93c5fd;border-radius:10px;border-top:5px solid #2563eb;">
    <strong style="display:block;font-size:12px;">SELECTOR S4 − S2</strong>
    <span style="font-size:22px;font-weight:800;">−1.71</span><br><span style="font-size:13px;">support-F1 points; 95% interval [−3.60, 0.21]</span>
  </div>
</div>

These are **descriptive, non-causal contrasts** from frozen historical artifacts;
they are not a leaderboard or a ranking of languages.

### Assignment geometry

| Descriptor | Observed | IID-uniform assignment expectation |
|---|---:|---:|
| Question differs from at least one gold paragraph | 99.811% | 99.826% |
| Two gold paragraphs use different languages | 95.598% | 95.833% |
| Question language absent from every candidate | 65.523% | 65.490% |
| Distinct candidate languages per item | 8.300 mean | 8.282 mean |

The expectations assume independent uniform assignment over 24 languages,
conditional on each item's realized candidate count. The close agreement is
consistent with the intended IID-uniform mixing geometry; it is not evidence of
equal translation quality across languages.

### Reader and selector sensitivity

Three 7,405-row oracle-evidence reader artifacts and one 7,405-row evidence-
selector artifact survive. The historically labeled Llama reader has 7,403
non-null outputs; its two missing outputs are scored as empty. Its endpoint
identity is not independently verified without the corresponding server log.
Reader rows receive annotated gold supporting sentences and therefore do not
evaluate evidence retrieval. Intervals in the following table use 10,000
item-level bootstrap replicates with seed `20260810`.

| System / metric | S2 | S3 | S4 | S4 − S2 (95% item-bootstrap interval) |
|---|---:|---:|---:|---:|
| Llama 3.1 70B label / answer F1 | 60.60 | 39.60 | 44.81 | −15.79 [−19.41, −12.12] |
| GPT-4o mini label / answer F1 | 57.79 | 47.34 | 47.54 | −10.25 [−13.75, −6.83] |
| Qwen2 72B label / answer F1 | 53.83 | 36.58 | 39.78 | −14.05 [−17.63, −10.46] |
| Adapted selector / support F1 | 85.93 | 86.26 | 84.22 | −1.71 [−3.60, 0.21] |

| System / metric | Question-to-gold: different-script − same-script-only |
|---|---:|
| Llama 3.1 70B label / answer F1 | −19.79 [−22.58, −16.99] |
| GPT-4o mini label / answer F1 | −11.98 [−14.70, −9.25] |
| Qwen2 72B label / answer F1 | −23.70 [−26.45, −20.91] |
| Adapted selector / support F1 | −1.78 [−3.20, −0.32] |

S2 contains one question-aligned gold paragraph; S4 places all gold evidence
outside the question language and across multiple languages. In these frozen
artifacts, the absolute descriptive reader contrasts are numerically larger than
the selector contrast. The question-to-gold script contrast compares 3,846
different-script items with 1,126 same-script-only items. Group composition is
not held fixed. Moreover, S0 has no observed validation items and the reader and
selector metrics are not directly commensurate; these contrasts neither estimate a
cross-lingual-versus-monolingual effect nor establish a causal module ranking.

### Assigned gold-paragraph language

Gold-paragraph language analyses use one row per HotpotQA source; paragraphs are
not treated as independent observations.

| Gold-language relation | Validation sources |
|---|---:|
| Same-language gold pair | 326 |
| Different-language, same-script pair | 2,006 |
| Different-script pair | 5,073 |

Across assigned gold languages, marginal reader F1 ranged from 34.6–51.1 for
the historical Llama label, 43.7–52.4 for the GPT-4o mini label, and 36.4–45.4
for the Qwen2 label; selector support F1 ranged from 81.8–86.1. These margins
mix question language, script, support role, and the second gold language.

A one-row-per-source F1 sensitivity model used all 7,405 items and represented
the two assigned gold-document languages as joint language counts, with English
as the substitution reference. It controlled question language, question type,
answer type, script relation, exact alignment, same-language pairing,
support-fact count, and structural flags. It used HC3 standard errors and
Benjamini–Hochberg correction within each outcome; marginal intervals used
2,000 bootstrap replicates. No
gold-language coefficient survived within-outcome FDR correction for
the GPT-4o mini label, Qwen2 label, or selector. Only the historical Llama label
retained four negative associations relative to substituting an English-assigned
gold paragraph. This supports **model-specific associations**, not a universal
ranking of languages or speaker communities.

## 🎯 Tasks and evaluation

<table>
  <tr>
    <td align="center"><b>🟣 Reader</b><br><sub>gold evidence → answer</sub></td>
    <td align="center"><b>🔵 Selector</b><br><sub>candidates → support</sub></td>
    <td align="center"><b>🟢 End to end</b><br><sub>candidates → support + answer</sub></td>
    <td align="center"><b>🟠 Diagnostics</b><br><sub>language and script strata</sub></td>
  </tr>
</table>

The released fields support:

- **Oracle-evidence reader:** predict the answer from gold supporting sentences.
- **Evidence selector:** identify supporting paragraphs or sentences among the
  supplied multilingual candidates.
- **End-to-end supplied-candidate QA:** jointly predict the answer and supporting
  facts.
- **Language-conditioned analysis:** stratify by question language, gold
  language, script relation, \\(\rho_G\\), \\(\rho_D\\), \\(H_G\\), or
  \\(K_C\\).

Recommended metrics are answer EM/F1, support EM/F1, and Hotpot-style joint
EM/F1. Report both micro averages and language-/condition-stratified results.
For Chinese, Japanese, and Thai, the repository evaluator uses character tokens;
English article removal is not applied to other languages. Always report missing
and unexpected prediction IDs.

### Minimum experiment report

For a result to be interpretable and reproducible, report all of the following:

- [ ] Hub configuration and pinned dataset revision;
- [ ] split, status filter, and exact evaluated denominator;
- [ ] answer, support, and joint metric implementation;
- [ ] normalization and tokenization policy by script;
- [ ] missing, duplicate, and unexpected prediction IDs;
- [ ] model identifier, served endpoint revision when available, prompt, and
      decoding parameters; and
- [ ] whether evidence was oracle-provided, selected from supplied candidates, or
      obtained through an external retriever.

## ✅ Intended uses

XHotpotQA is intended for research on:

- cross-language evidence composition;
- multilingual evidence selection;
- transfer and adaptation across scripts;
- answer-language control;
- robustness to multilingual distractors; and
- explainable multi-hop QA with supplied candidates.

The resource should not be used to rank languages, cultures, countries, or
speaker communities. A model score combines reasoning, translation artifacts,
tokenization, script handling, and source-domain effects.

## ⛔ Out-of-scope and responsible use

XHotpotQA is a research benchmark, not a production factuality or safety
certification. Unsupported uses include making high-stakes decisions about
people, treating assigned-language margins as measures of a language's
intrinsic difficulty, and presenting machine-translated examples as naturally
authored text. Systems evaluated here may still hallucinate answers, exploit
source artifacts, or fail on naturally occurring code-switching.

The source material is derived from Wikipedia through HotpotQA and may mention
real people or organizations. Downstream users remain responsible for reviewing
generated outputs, respecting the data license, and documenting any additional
translation, filtering, or annotation.

## ⚖️ Limitations and biases

- **English-origin content.** Questions and evidence originate in English
  Wikipedia through HotpotQA; they are not naturally authored information needs
  in the target languages.
- **Machine translation.** Translationese, entity/transliteration variation,
  answer leakage, polarity errors, and unequal semantic adequacy may affect
  difficulty.
- **Recovered provenance.** The exact historical provider revision and random
  assignment seed are unavailable.
- **Known V1 defects.** Structural issues are retained and labeled. Semantic
  adequacy is not established by the structural audit.
- **Synthetic mixing.** Independent paragraph-language assignment is a
  controlled stress test, not a frequency model of real multilingual
  information environments.
- **Fixed candidates.** The benchmark does not measure open-corpus retrieval.
- **HotpotQA artifacts.** Some source questions may be solvable from one hop or
  parametric knowledge; evidence-necessity checks remain advisable.
- **Metric sensitivity.** Unicode normalization, segmentation, transliteration,
  and script can change answer overlap scores.
- **Incomplete parallel release.** Paired question-language causal contrasts
  require the prospective complete XHotpotQA+ validation mapping or V2; they
  cannot be claimed from this one-view release.

## 🔒 Release integrity and manifest

[`RELEASE_MANIFEST_V1_1.json`](https://huggingface.co/datasets/Iman998/XhotpotQA/blob/1d29e7918cf1acc045726c70fddba82371833090/RELEASE_MANIFEST_V1_1.json)
is the machine-readable authority for the frozen audited-V1.1 data snapshot. It records:

- release version and train selection rule;
- split-level source counts;
- `status_counts`, `flag_counts`, and question-language counts;
- every Parquet shard's relative path, row count, byte size, and SHA-256; and
- total rows and bytes.

The companion software is frozen at
[**GitHub release `v0.4.1`**](https://github.com/Iman998/XhotpotQA/tree/v0.4.1).
The code tag and frozen Hub data revision serve different purposes: the former
fixes the toolkit, while the latter fixes the released Parquet bytes.

Each row additionally carries
`provenance.source_record_sha256`,
`provenance.legacy_raw_sha256`, and `record_sha256`: respectively,
fingerprints of the joined HotpotQA source record, the recovered four-field
legacy payload, and the canonical released row. Consumers should pin a Hub
revision for experiments and archive the manifest with predictions.

<details>
<summary><b>Load and inspect the release manifest in Python</b></summary>

```python
from huggingface_hub import hf_hub_download
import json

manifest_path = hf_hub_download(
    repo_id="Iman998/XhotpotQA",
    repo_type="dataset",
    filename="RELEASE_MANIFEST_V1_1.json",
    revision="1d29e7918cf1acc045726c70fddba82371833090",
)

with open(manifest_path, encoding="utf-8") as stream:
    manifest = json.load(stream)

print(manifest["release_version"])
print(manifest["train"]["status_counts"])
print(manifest["validation"]["flag_counts"])
```

</details>

## Release family

Browse the pinned dataset and audit releases together in the
[XHotpotQA cross-lingual multi-hop QA collection](https://huggingface.co/collections/Iman998/xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a).

## License

The dataset files are adaptations of [HotpotQA](https://hotpotqa.github.io/) and
are distributed under
[**CC BY-SA 4.0**](https://creativecommons.org/licenses/by-sa/4.0/). Users must
attribute XHotpotQA and the original HotpotQA work,
identify modifications, and preserve the ShareAlike requirements. Repository
software is licensed separately under the MIT License.

## Citation

If you use the resource, cite both XHotpotQA and HotpotQA:

```bibtex
@misc{barati2026xhotpotqa,
  title  = {XHotpotQA: A Benchmark for Cross-Lingual Knowledge Composition
            in Multi-Hop Question Answering},
  author = {Barati, Iman and Ghafouri, Arash and
            Minaei-Bidgoli, Behrouz},
  year   = {2026},
  howpublished = {Hugging Face dataset},
  url    = {https://huggingface.co/datasets/Iman998/XhotpotQA},
  note   = {Audited V1.1 data snapshot, revision
            1d29e7918cf1acc045726c70fddba82371833090; code v0.4.1;
            manuscript in preparation}
}

@inproceedings{yang2018hotpotqa,
  title     = {HotpotQA: A Dataset for Diverse, Explainable Multi-hop
               Question Answering},
  author    = {Yang, Zhilin and Qi, Peng and Zhang, Saizheng and Bengio,
               Yoshua and Cohen, William W. and Salakhutdinov, Ruslan and
               Manning, Christopher D.},
  booktitle = {Proceedings of EMNLP},
  year      = {2018},
  doi       = {10.18653/v1/D18-1259}
}
```

## 👥 Maintainers and resources

- **Iman Barati** — methodology and resource construction
- Arash Ghafouri — supervision
- Behrouz Minaei-Bidgoli — supervision and validation

Code, generation, evaluation, and audit tooling:
[GitHub release `v0.4.1`](https://github.com/Iman998/XhotpotQA/tree/v0.4.1)

Public audited V1 data:
[huggingface.co/datasets/Iman998/XhotpotQA](https://huggingface.co/datasets/Iman998/XhotpotQA)
(preferred configuration `xhotpotqa_v1_1_audited`; frozen V1.1 data revision
`1d29e7918cf1acc045726c70fddba82371833090`). The immutable earlier configuration
`xhotpotqa_v1_audited` remains available at revision
`52b8bee41ff2bb0d41cd400ff5646c0e800b5127`.

A persistent manuscript archive link will be added after deposit. Until then,
cite the versioned Hub revision and preserve its `RELEASE_MANIFEST.json`.

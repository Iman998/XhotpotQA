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
- hotpotqa/hotpot_qa
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
- config_name: xhotpotqa_v1_audited
  default: true
  data_files:
  - split: train
    path: data/xhotpotqa_v1_audited/train-*.parquet
  - split: validation
    path: data/xhotpotqa_v1_audited/validation-*.parquet
---

<div align="center">

# XHotpotQA

### Cross-lingual multi-hop question answering over mixed-language evidence

One question. Multiple evidence paragraphs. Languages may change between hops.

[![Release](https://img.shields.io/badge/release-recovered%20V1-f59e0b?style=flat-square)](#release-status)
[![Audit](https://img.shields.io/badge/audit-status%20preserved-2563eb?style=flat-square)](#quality-audit)
[![Format](https://img.shields.io/badge/format-Parquet-7c3aed?style=flat-square)](#data-format)
[![License](https://img.shields.io/badge/data-CC%20BY--SA%204.0-16a34a?style=flat-square)](#license)
[![Code](https://img.shields.io/badge/code-GitHub-111827?style=flat-square)](https://github.com/Iman998/XhotpotQA)

</div>

XHotpotQA is a controlled benchmark for studying whether a system can select and
compose evidence when the question, gold paragraphs, and distractors are not
necessarily written in the same language. It adapts the fixed-candidate HotpotQA
distractor task to 24 languages while retaining paragraph order, sentence
boundaries, question type, difficulty, answers, and sentence-level supporting
facts.

This Hub revision is deliberately named **`xhotpotqa_v1_audited`**. It is a
recovered, audit-preserving V1 resource—not the prospective canonical V2. Every
source item is retained, including rows with known structural defects, and every
row carries a machine-readable `status` and `structural_flags` field.

## Dataset at a glance

| Train sources | Validation sources | Released rows | Languages |
|---:|---:|---:|---:|
| **15,661** | **7,405** | **23,066** | **24** |

| Property | Value |
|---|---|
| Task | Fixed-candidate cross-lingual multi-hop QA |
| Source | HotpotQA distractor; hard-only train and full distractor validation |
| Evidence | Ordered candidate paragraphs with sentence boundaries |
| Supervision | Answer plus sentence-level supporting facts |
| Current configuration | `xhotpotqa_v1_audited` |
| Storage | Sharded, Zstandard-compressed Parquet |
| Unit of release | One recovered view per HotpotQA source |

## Release status

| Artifact | Status | What is available |
|---|---|---|
| **Audited V1 base** | **Available in this Hub revision** | 15,661 train rows and all 7,405 validation rows |
| **XHotpotQA+** | **Prospective** | The historical archive contains 375,864 train views, but the 177,720-view parallel validation mapping is not available; no `xhotpotqa_plus` Hub configuration is published |
| **Canonical V2** | **Prospective / blocked on completed artifacts and audit** | A model-agnostic OpenAI-compatible regeneration pipeline exists, but V2 data and a paired V1–V2 quality study are not part of this release |

> **Important:** `status="quarantined"` is a data-quality label, not an
> exclusion. Quarantined rows remain in the released splits so that counts,
> source alignment, and reported analyses are reproducible. Users must state
> whether they evaluate the complete split or a status-filtered subset.

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

## Quickstart

Install a recent version of `datasets`, then load the single public
configuration:

```bash
pip install -U datasets
```

```python
from datasets import load_dataset

dataset = load_dataset(
    "iman998/XhotpotQA",
    "xhotpotqa_v1_audited",
)

print(dataset)
print(len(dataset["train"]))       # 15_661
print(len(dataset["validation"]))  # 7_405

row = dataset["validation"][0]
print(row["question_language"], row["question"])
print(row["status"], row["structural_flags"])
print(row["supporting_facts"])
```

For low-memory inspection, stream Parquet shards:

```python
from datasets import load_dataset

stream = load_dataset(
    "iman998/XhotpotQA",
    "xhotpotqa_v1_audited",
    split="validation",
    streaming=True,
)

first = next(iter(stream))
print(first["source_id"], first["question_language"])
```

For a strict sensitivity subset, filter by `status` and always report the
resulting denominator:

```python
validation = dataset["validation"]
accepted_only = validation.filter(lambda row: row["status"] == "accepted")

print(
    {
        status: validation.filter(lambda row: row["status"] == status).num_rows
        for status in ("accepted", "review_required", "quarantined")
    }
)
```

The complete 7,405-row validation split should remain the primary denominator
when reproducing the frozen V1 analyses. The accepted-only view is a sensitivity
analysis, not a replacement test split.

## Data format

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
position. `source_title` retains the original HotpotQA annotation key while
`title` stores its translated form. Supporting facts are joined through the
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
`language`. These assignments are not human quality certifications.

## Construction and provenance

The released configuration is reconstructed from historical translation shards
that used pandas `orient="columns"` JSON and did not carry HotpotQA IDs or
support labels. The release builder performs this audited transformation:

```text
Official HotpotQA source snapshot
              │
              ├── ordered join ── recovered V1 translation shards
              │
              ▼
     source IDs + source metadata + support labels
              │
              ├── deterministic train-view selection
              ├── structural audit with no silent repair
              ▼
      status-bearing Parquet rows + release manifest
```

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

### Deterministic public train selection

The historical base mapping was random and its seed was not preserved. It cannot
be reproduced exactly from the surviving archive. To make this public one-view
release reproducible, the selected training view is:

\[
v_i =
\operatorname{int}\!\left(
\operatorname{SHA256}
(\texttt{"xhotpotqa-public-v1|"} \Vert \texttt{source\_id}_i)[0{:}8]
\right) \bmod 24.
\]

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

The prospective V2 pipeline is model-agnostic and uses an OpenAI-compatible API;
any compatible model can be served, including through vLLM. A Gemma setup is an
example configuration, not a requirement and not evidence that V2 has already
been generated or validated.

## Quality audit

### What the status field means

| Status | Interpretation |
|---|---|
| `accepted` | No release-blocking structural flag was found by the automated audit |
| `review_required` | A non-blocking ambiguity requires explicit review |
| `quarantined` | At least one release-blocking structural defect was preserved |

These labels describe **structural validity under the implemented checks**. They
do not certify semantic translation adequacy, fluency, cultural suitability, or
paper acceptance.

The validator checks candidate cardinality and shape, sentence preservation,
blank content, support-title resolution, support-index bounds, normalized title
collisions, and question/answer presence. `structural_flags` stores the exact
findings, including flags such as
`paragraph_sentence_shortfall`,
`paragraph_sentence_surplus`, `blank_sentence`,
`support_index_out_of_range`, and
`duplicate_normalized_translated_title`.

### Audited validation findings

The recovered validation audit retains all 7,405 sources:

| Finding | Count | Counting unit |
|---|---:|---|
| Outside the union of release-blocking flags | **6,966** | source rows |
| In the union of release-blocking flags | **439** (5.93%) | source rows |
| Sentence-cardinality mismatch | 424 | paragraph events affecting 407 rows |
| At least one blank translated sentence | 33 | source rows |
| Unavailable translated support index | 9 | source rows |
| Duplicate normalized translated title | 4 | source rows |

Component sets overlap and therefore must not be added. The four
duplicate-title rows are non-blocking `review_required` records, so they belong
to the 6,966 rows outside the release-blocking union rather than to the 439-row
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

### Sensitivity to the validation quality gate

Removing the 439 flagged validation items changed every tested aggregate EM/F1
metric by at most **0.51 points** and either primary language-condition contrast
by at most **0.22 points**. All eight item-bootstrap intervals for the
clean-minus-complete contrast shifts included zero. This indicates that the
reported V1 language-alignment pattern is not concentrated in the flagged
subset; it does **not** make the underlying defects acceptable.

## Cross-lingual descriptors

Let \(L_q\) be the question language, \(G\) the gold-paragraph set,
\(D\) the distractor set, and \(L_p\) the assigned language of paragraph
\(p\). XHotpotQA reports:

\[
\rho_G =
\frac{1}{|G|}
\sum_{p\in G}\mathbf{1}[L_p \neq L_q],
\qquad
\rho_D =
\frac{1}{|D|}
\sum_{p\in D}\mathbf{1}[L_p \neq L_q].
\]

When an item has no distractors, \(\rho_D\) is not applicable rather than
zero. The analysis also derives normalized gold-evidence language entropy
\(H_G\), candidate-language count \(K_C\), question-to-gold script
relation, and these realized strata:

| Stratum | Definition | Validation count |
|---|---|---:|
| S0 | Gold and distractors fully aligned with the question | 0 |
| S1 | Gold aligned; multilingual distractors | 14 |
| S2 | Partial gold mismatch, \(0<\rho_G<1\) | 564 |
| S3 | Full gold mismatch in one evidence language | 312 |
| S4 | Full gold mismatch across multiple evidence languages | 6,515 |

S1 is too small for inferential comparison, and S0 is unpopulated in this
realized validation assignment.

## Artifact-verified validation analysis

The following statistics were recomputed from the recovered 7,405-row validation
metadata and surviving prediction artifacts. They are frozen-run descriptive
associations—not a leaderboard and not causal estimates of language effects.

### Assignment geometry

| Descriptor | Observed | IID assignment expectation |
|---|---:|---:|
| Question differs from at least one gold paragraph | 99.811% | 99.826% |
| Two gold paragraphs use different languages | 95.598% | 95.833% |
| Question language absent from every candidate | 65.523% | 65.490% |
| Distinct candidate languages per item | 8.300 mean | 8.282 mean |

The close observed/expected agreement supports the intended high-mixing geometry;
it is not evidence of equal translation quality across languages.

### Reader and selector sensitivity

Three 7,405-row oracle-evidence reader artifacts and one 7,405-row evidence-
selector artifact survive. The historically labeled Llama reader has 7,403
non-null outputs; its two missing outputs are scored as empty. Its endpoint
identity is not independently verified without the corresponding server log.

| System / metric | S2 | S3 | S4 | S4 − S2 (95% item-bootstrap interval) | Different − same script |
|---|---:|---:|---:|---:|---:|
| Llama 3.1 70B label / answer F1 | 60.60 | 39.60 | 44.81 | −15.79 [−19.41, −12.12] | −19.79 [−22.58, −16.99] |
| GPT-4o mini label / answer F1 | 57.79 | 47.34 | 47.54 | −10.25 [−13.75, −6.83] | −11.98 [−14.70, −9.25] |
| Qwen2 72B label / answer F1 | 53.83 | 36.58 | 39.78 | −14.05 [−17.63, −10.46] | −23.70 [−26.45, −20.91] |
| Adapted selector / support F1 | 85.93 | 86.26 | 84.22 | −1.71 [−3.60, 0.21] | −1.78 [−3.20, −0.32] |

S2 contains one question-aligned gold paragraph; S4 places all gold evidence
outside the question language and across multiple languages. In these frozen
artifacts, the mismatch is associated much more strongly with answer composition
from oracle evidence than with selecting evidence among supplied candidates.
Group composition is not held fixed.

### Assigned gold-paragraph language

Gold-paragraph language analyses use one row per HotpotQA source; paragraphs are
not treated as independent observations.

| Gold-language relation | Validation sources |
|---|---:|
| Same-language gold pair | 326 |
| Different-language, same-script pair | 2,006 |
| Different-script pair | 5,073 |

Marginal reader F1 ranges were 34.6–51.1, 43.7–52.4, and 36.4–45.4 across
assigned gold languages for the three reader artifacts; selector support F1
ranged from 81.8–86.1. These margins mix question language, script, support
role, and the second gold language.

A one-row-per-source sensitivity model jointly represented both gold languages
and controlled question language, question type, answer type, script relation,
exact alignment, same-language pairing, support-fact count, and structural
flags. No gold-language coefficient survived within-outcome FDR correction for
the GPT-4o mini label, Qwen2 label, or selector. Only the historical Llama label
retained four negative associations relative to substituting an English-assigned
gold paragraph. This supports **model-specific associations**, not a universal
ranking of languages or speaker communities.

## Tasks and evaluation

The released fields support:

- **Oracle-evidence reader:** predict the answer from gold supporting sentences.
- **Evidence selector:** identify supporting paragraphs or sentences among the
  supplied multilingual candidates.
- **End-to-end fixed-candidate QA:** jointly predict the answer and supporting
  facts.
- **Language-conditioned analysis:** stratify by question language, gold
  language, script relation, \(\rho_G\), \(\rho_D\), \(H_G\), or
  \(K_C\).

Recommended metrics are answer EM/F1, support EM/F1, and Hotpot-style joint
EM/F1. Report both micro averages and language-/condition-stratified results.
For Chinese, Japanese, and Thai, the repository evaluator uses character tokens;
English article removal is not applied to other languages. Always report missing
and unexpected prediction IDs.

## Intended uses

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

## Limitations and biases

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

## Release integrity and manifest

`RELEASE_MANIFEST.json` is the machine-readable authority for this Hub
revision. It records:

- release version and train selection rule;
- split-level source counts;
- `status_counts`, `flag_counts`, and question-language counts;
- every Parquet shard's relative path, row count, byte size, and SHA-256; and
- total rows and bytes.

Each row additionally carries
`provenance.source_record_sha256`,
`provenance.legacy_raw_sha256`, and `record_sha256`: respectively,
fingerprints of the joined HotpotQA source record, the recovered four-field
legacy payload, and the canonical released row. Consumers should pin a Hub
revision for experiments and archive the manifest with predictions.

```python
from huggingface_hub import hf_hub_download
import json

manifest_path = hf_hub_download(
    repo_id="iman998/XhotpotQA",
    repo_type="dataset",
    filename="RELEASE_MANIFEST.json",
)

with open(manifest_path, encoding="utf-8") as stream:
    manifest = json.load(stream)

print(manifest["release_version"])
print(manifest["train"]["status_counts"])
print(manifest["validation"]["flag_counts"])
```

## License

The dataset files are adaptations of HotpotQA and are distributed under
**CC BY-SA 4.0**. Users must attribute XHotpotQA and the original HotpotQA work,
identify modifications, and preserve the ShareAlike requirements. Repository
software is licensed separately under the MIT License.

## Citation

If you use the resource, cite both XHotpotQA and HotpotQA:

```bibtex
@unpublished{barati2026xhotpotqa,
  title  = {XHotpotQA: A Benchmark for Cross-Lingual Multi-Hop Question
            Answering over Mixed-Language Evidence},
  author = {Barati, Iman and Ghafouri, Arash and Minaei-Bidgoli, Behrouz},
  year   = {2026},
  note   = {Manuscript and resource release in preparation}
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

## Maintainers and resources

- **Iman Barati** — methodology and resource construction
- Arash Ghafouri — supervision and manuscript review
- Behrouz Minaei-Bidgoli — supervision and manuscript review

Code, generation, evaluation, and audit tooling:
[github.com/Iman998/XhotpotQA](https://github.com/Iman998/XhotpotQA)

A persistent manuscript archive link will be added after deposit. Until then,
cite the versioned Hub revision and preserve its `RELEASE_MANIFEST.json`.

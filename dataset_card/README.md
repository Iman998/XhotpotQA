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
- supporting-fact-identification
- evidence-selection
- synthetic-translation
size_categories:
- 10K<n<100K
- 100K<n<1M
configs:
- config_name: xhotpotqa
  default: true
  data_files:
  - split: train
    path: data/xhotpotqa/train.jsonl
  - split: validation
    path: data/xhotpotqa/validation.jsonl
- config_name: xhotpotqa_plus
  data_files:
  - split: train
    path: data/xhotpotqa_plus/train.jsonl
  - split: validation
    path: data/xhotpotqa_plus/validation.jsonl
---

# XHotpotQA

XHotpotQA is a 24-language benchmark for **cross-lingual multi-hop question answering
over mixed-language evidence**. It transforms the fixed-candidate HotpotQA distractor task
while retaining ordered paragraphs, sentence boundaries, answers, question type, difficulty,
and sentence-level supporting facts.

The key design choice is within-instance language mixing: the question and answer share one
language, while each candidate paragraph independently receives a language. A system may
therefore need to resolve a bridge fact in one language, compose it with answer-bearing
evidence in another, ignore multilingual distractors, and answer in the question language.

## Dataset at a glance

| Configuration | Train | Validation | Total |
|---|---:|---:|---:|
| XHotpotQA | 15,661 | 7,405 | 23,066 |
| XHotpotQA+ | 375,864 | 177,720 | 553,584 |

The public dataset deposit is pending. The paths in the YAML front matter are the exact paths
validated by the release tooling and become loadable after publication.

## Languages

| Code | Language | Primary script | Family/branch |
|---|---|---|---|
| ar | Arabic | Arabic | Semitic |
| bn | Bengali | Bengali | Indo-Aryan |
| de | German | Latin | Germanic |
| el | Greek | Greek | Hellenic |
| en | English | Latin | Germanic |
| es | Spanish | Latin | Romance |
| fa | Persian | Arabic | Iranian |
| fr | French | Latin | Romance |
| hi | Hindi | Devanagari | Indo-Aryan |
| id | Indonesian | Latin | Austronesian |
| it | Italian | Latin | Romance |
| ja | Japanese | Japanese | Japonic |
| ko | Korean | Hangul | Koreanic |
| nl | Dutch | Latin | Germanic |
| pl | Polish | Latin | Slavic |
| pt | Portuguese | Latin | Romance |
| ru | Russian | Cyrillic | Slavic |
| sv | Swedish | Latin | Germanic |
| sw | Swahili | Latin | Bantu |
| th | Thai | Thai | Kra-Dai |
| tr | Turkish | Latin | Turkic |
| ur | Urdu | Arabic | Indo-Aryan |
| vi | Vietnamese | Latin | Austroasiatic |
| zh | Mandarin Chinese | Han | Sinitic |

Language codes follow ISO 639-1. Script/family labels are descriptive analysis metadata;
they do not imply comparable resource levels or translation quality.

## Usage

```python
from datasets import load_dataset

base = load_dataset("iman998/XHotpotQA", "xhotpotqa")
parallel = load_dataset("iman998/XHotpotQA", "xhotpotqa_plus")

example = base["validation"][0]
print(example["question"], example["question_language"])
print(example["supporting_facts"])

# Join paired views by source_id; do not treat all 24 views as independent samples.
paired_example = parallel["validation"][0]
print(paired_example["source_id"], paired_example["question_language"])
```

## Record schema

```text
id: string
source_id: string
source_split: train | validation
question: string
answer: string
question_language: ISO 639-1
answer_language: ISO 639-1
question_type: bridge | comparison
difficulty: hard | medium | easy
candidates: list[
  id: string
  title: string
  sentences: list[string]
  language: ISO 639-1
  source_title: string
  source_sentences: list[string]
]
supporting_facts: list[
  paragraph_id: string
  sentence_id: int
  role: bridge | answer | comparison | support
]
provenance: struct[
  schema_version: string
  source_dataset: string
  source_license: string
  assignment_version: string
  seed: int
  translation_model: string
  translation_revision: string
  prompt_version: string
  prompt_hash: SHA-256
  retry_count: int
  created_at: string
  validation_status: string
  decoding: mapping
]
checksum: SHA-256
```

Paragraph IDs, sentence indices, and order are immutable. Translated titles are never used
as annotation keys. The checksum covers the canonical semantic record; `created_at`,
`retry_count`, and `validation_status` are excluded because they describe execution rather
than content. See the repository schema document for exact invariants.

## Construction

1. Source records come from HotpotQA's distractor configuration.
2. Training retains 15,661 `hard` items; validation contains all 7,405 distractor items.
3. The question–answer pair receives one language; every candidate title and paragraph
   receives an independently sampled language from the 24-language inventory.
4. Titles, sentence arrays, questions, and answers are translated while their IDs and
   supporting-fact indices remain fixed.
5. Automatic checks reject missing/merged sentences, invalid language codes, broken support
   indices, empty content, question/answer language disagreement, duplicate IDs, and checksum
   mismatches.

The historical translator-selection pilot compared GPT-4o, GPT-4o mini, and Llama 3.1 70B.
GPT-4o mini was selected after a Persian specialist comparison and a small 23-language
follow-up. GPT model references are frozen to the versions available in January 2025
(`gpt-4o-2024-11-20` and `gpt-4o-mini-2024-07-18`). This pilot is not a substitute for a
stratified bilingual audit of the released translations.

Raw model responses may be retained through the opt-in audit writer during generation. That
log can contain source text and model output, is not a dataset field, and must remain outside
the public release unless a separate review explicitly authorizes disclosure.

## XHotpotQA+ derived views

The `xhotpotqa_plus` configuration deterministically pairs every base record with all 24 available
question--answer translations while keeping evidence and supervision fixed. A complete input
mapping yields 375,864 training views and 177,720 validation views (553,584 total), grouped by
`source_id` with IDs of the form `<base-id>--qa-<language>`. The default `xhotpotqa`
configuration retains the 23,066 canonical base records. The release gate verifies every
parallel view against its base record and rejects changed evidence, supervision, provenance,
ordering, IDs, or language coverage. Each view inherits base-record provenance, so the
checksum and generation metadata for the separate question--answer translation mapping must
be retained as a companion artifact.

## Cross-lingual descriptors

For question language \(L_q\), gold paragraph set \(G\), and distractor set \(D\), the
analysis library exposes:

\[
\rho_G=|G|^{-1}\sum_{p\in G}\mathbf{1}[L_p\neq L_q],\qquad
\rho_D=|D|^{-1}\sum_{p\in D}\mathbf{1}[L_p\neq L_q].
\]

It also derives normalized gold-evidence entropy \(H_G\), the number of distinct candidate
languages \(K_C\), same-, mixed-, or different-script relations between the question and gold
evidence, and five mutually exclusive strata: fully monolingual, multilingual distractors
only, partial gold mismatch, full mismatch with one evidence language, and full mismatch with
multilingual evidence.

## Supported tasks and metrics

- **Reader:** answer from gold supporting evidence.
- **Evidence selector:** predict supporting paragraphs/sentences among supplied distractors.
- **End-to-end:** jointly predict the answer and supporting facts.

The evaluator includes answer EM/precision/recall/F1, supporting-fact
EM/precision/recall/F1, and Hotpot-style joint metrics. It reports micro aggregates, macro
EM/F1 by question language, per-language and script-relation aggregates, the five language
conditions, descriptor summaries, and stable bins for \(\rho_G\), \(\rho_D\), \(H_G\), and
\(K_C\). It also reports missing and unexpected prediction counts. For Chinese, Japanese,
and Thai, answer F1 uses character tokens; English article removal is not applied to other
languages.

## Release integrity

The uploader validates exact split cardinalities, unique IDs, schema invariants, source
metadata, provenance fields, semantic checksums, and the base-to-parallel derivation before
network access. The dataset card, all four JSONL files, and a generated `manifest.json` are
then published in one Hub commit. The manifest records each configuration and split's path,
record count, byte size, and SHA-256 hash, plus toolkit/data versions, the code revision, and
the `pyproject.toml` hash. It does not contain the private raw response audit log.

## Intended uses

XHotpotQA is intended for controlled research on multilingual evidence selection,
cross-language composition, transfer learning, output-language control, and explainable
multi-hop QA. It is not a full-Wikipedia retrieval benchmark because candidate paragraphs
are supplied. It should not be used to rank languages, cultures, or speaker communities.

## Limitations and biases

- The content originates in English Wikipedia and does not represent naturally authored
  information needs in the target languages.
- Machine translation may introduce translationese, entity variants, answer leakage,
  unequal quality, or script-specific metric artifacts.
- Independent language assignment creates a controlled stress test rather than a frequency
  model of real multilingual information environments.
- HotpotQA may contain questions solvable with one hop or parametric knowledge. Partial-
  evidence and necessity analyses are recommended.
- Aggregate scores can hide large language and script gaps. Report per-language and
  mismatch-conditioned results.

## Licensing

Dataset files are adaptations of HotpotQA and are distributed under **CC BY-SA 4.0**.
Attribute both XHotpotQA and the original HotpotQA work, identify modifications, and retain
ShareAlike requirements. Repository software uses a separate MIT license.

## Citation

```bibtex
@unpublished{barati2026xhotpotqa,
  title   = {XHotpotQA: A 24-Language Benchmark for Cross-Lingual Multi-Hop
             Question Answering over Mixed-Language Evidence},
  author  = {Barati, Iman and Ghafouri, Arash and Minaei-Bidgoli, Behrouz},
  year    = {2026},
  note    = {Manuscript and resource release in preparation}
}

@inproceedings{yang2018hotpotqa,
  title     = {HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering},
  author    = {Yang, Zhilin and others},
  booktitle = {EMNLP},
  year      = {2018},
  doi       = {10.18653/v1/D18-1259}
}
```

## Maintainers

- Iman Barati — Iran University of Science and Technology
- Arash Ghafouri — Iran University of Science and Technology
- Behrouz Minaei-Bidgoli — Iran University of Science and Technology

The public code repository and persistent manuscript archive identifiers are pending deposit.
This notice will be replaced with their exact records after publication.

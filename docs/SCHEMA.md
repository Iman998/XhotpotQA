# Canonical schema

Each JSONL record contains:

- `id`: immutable XHotpotQA ID.
- `source_id`, `source_split`, `question_type`, `difficulty`: source provenance.
- `question`, `answer`, `question_language`, `answer_language`.
- `candidates`: ordered paragraph objects with `id`, `title`, `sentences`, `language`, and
  optional English source fields.
- `supporting_facts`: ordered `{paragraph_id, sentence_id, role}` objects. `role` is one of
  `bridge`, `answer`, `comparison`, or `support`.
- `provenance`: schema and assignment versions, seed, model ID/revision, prompt version/hash,
  decoding parameters, parser-retry count, creation timestamp, structural-validation status,
  source dataset, and source license.
- `checksum`: SHA-256 over the canonical semantic payload. Volatile execution fields
  (`created_at`, retry count, and validation status) are excluded.

Candidate and sentence order are semantic. A translation must not add, delete, merge, or
reorder sentences. Supporting facts use immutable paragraph IDs rather than translated
titles so title translation cannot break supervision. The Python model permits omitted English
source fields for development and historical reads; the strict public-release gate requires a
non-empty `source_title` and a `source_sentences` array for every candidate.

## XHotpotQA+ views

XHotpotQA+ uses the same record schema. For each base record and each language `ll` in the
canonical 24-language inventory, its variant has:

- `id = <base-id>--qa-<ll>`;
- the unchanged `source_id`, `source_split`, candidates, supporting facts, task metadata, and
  provenance;
- the `ll` question and answer translations, with both language fields set to `ll`; and
- a newly computed semantic checksum.

The inherited provenance describes construction of the base record and its evidence. Because
the question--answer translation mapping is a separate input, its checksum and generation
metadata must be preserved as a companion release artifact; the expansion command does not
rewrite base provenance to describe that external mapping.

The language order is the order of `LANGUAGE_CODES`, not JSON object insertion order. Thus
identical ordered base JSONL and translation-map inputs produce byte-identical output across
runs. See [`XHOTPOTQA_PLUS.md`](XHOTPOTQA_PLUS.md) for the input contract and release
cardinalities. The derived records are published under the `xhotpotqa_plus` Hugging Face
configuration; `xhotpotqa` is the default base configuration.

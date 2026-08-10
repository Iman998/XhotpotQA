# Canonical schema

Each JSONL record contains:

- `id`: immutable XHotpotQA ID.
- `source_id`, `source_split`, `question_type`, `difficulty`: source provenance.
- `question`, `answer`, `question_language`, `answer_language`.
- `candidates`: ordered paragraph objects with `id`, `title`, `sentences`, `language`, and
  optional English source fields.
- `supporting_facts`: ordered `{paragraph_id, sentence_id, role}` objects. `role` is one of
  `bridge`, `answer`, `comparison`, or `support`.
- `provenance`: assignment version, seed, model ID/revision, prompt version, decoding
  parameters, creation timestamp, and source license.
- `checksum`: SHA-256 over the canonical semantic payload.

Candidate and sentence order are semantic. A translation must not add, delete, merge, or
reorder sentences. Supporting facts use immutable paragraph IDs rather than translated
titles so title translation cannot break supervision.


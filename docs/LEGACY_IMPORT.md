# Audited legacy import

The historical translation shards store four pandas-oriented columns:
`translate_context`, `translate_question`, `translate_answer`, and `target_language`.
They omit immutable source IDs and supporting facts. A defensible conversion therefore
requires an ordered join to a checksum-pinned HotpotQA JSON array; copying or concatenating
the shard text directly is not a canonical release.

## Contracts

- Validation expects one translated row for each of 7,405 source records.
- Training selects the 15,661 `hard` source records and expects exactly 24 consecutive views
  per source in the historical language order.
- All 24 training views for a source must have byte-equivalent context values.
- Candidate counts must match the source, and every support title must resolve to one ordered
  candidate.
- Sentence cardinality, non-empty fields, language inventory, and support bounds are strict.
- The original files and their SHA-256 digests remain immutable.

## Outputs

The importer writes a new directory atomically:

- `canonical.jsonl`: records that pass every structural gate;
- `raw_manifest.json`: input hashes, source-order hash, counts, provenance limitations, and
  output hashes;
- `quarantine_manifest.jsonl`: content hashes and locators for rejected raw rows, without
  duplicating their translated text; and
- `correction_manifest.jsonl`: pending or applied content-addressed corrections.

A correction is a full canonical replacement keyed by `legacy_id` and the exact raw-row
SHA-256. It may repair translated content but cannot change source identity, candidate order,
source evidence, or supporting-fact supervision. Never modify the raw archive in place.

## Release rule

Exit status is nonzero while quarantine is non-empty. A Hub upload remains blocked until all
required counts, checksums, base/parallel derivation invariants, and correction records pass.
The historical unseeded base-train projection and missing parallel validation views must be
recovered or regenerated under a separately named version; they must not be inferred silently.

# Changelog

## 0.3.0 - 2026-08-11

- Add deterministic, atomic construction of all 24 XHotpotQA+ question--answer views from
  canonical base records and source-ID keyed translations.
- Add `expand-plus`, strict canonical cardinality gates, JSON/JSONL input contracts, and
  integrity tests for fixed evidence, provenance, IDs, and checksums.
- Publish XHotpotQA+ as a second Hugging Face configuration, with streaming validation
  against the base data and an atomic four-file Hub release manifest.
- Add a streaming, checksum-pinned importer for the historical pandas-column shards, with
  content-addressed corrections, quarantine manifests, and strict ordered joins to HotpotQA.
- Version the evaluation normalization contract and add Unicode/script-aware answer scoring,
  script-relation summaries, mismatch/entropy bins, and an explicit no-distractor/NA stratum.
- Make V2 generation model-agnostic through a generic OpenAI-compatible configuration and
  vLLM serving script; retain the Gemma configuration only as an optional example.

## 0.2.0 - 2026-08-10

- Added a deterministic, resumable model-agnostic OpenAI-compatible generation pipeline,
  with a Gemma configuration retained only as an example.
- Added canonical JSONL validation and release gates.
- Added answer, support, joint, and language-mismatch evaluation.
- Added a Hugging Face dataset card and upload workflow.

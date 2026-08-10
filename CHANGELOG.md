# Changelog

## Unreleased

- Add deterministic, atomic construction of all 24 XHotpotQA+ question--answer views from
  canonical base records and source-ID keyed translations.
- Add `expand-plus`, strict canonical cardinality gates, JSON/JSONL input contracts, and
  integrity tests for fixed evidence, provenance, IDs, and checksums.
- Publish XHotpotQA+ as a second Hugging Face configuration, with streaming validation
  against the base data and an atomic four-file Hub release manifest.

## 0.2.0 - 2026-08-10

- Added a deterministic, resumable Gemma 4 31B generation pipeline.
- Added canonical JSONL validation and release gates.
- Added answer, support, joint, and language-mismatch evaluation.
- Added a Hugging Face dataset card and upload workflow.

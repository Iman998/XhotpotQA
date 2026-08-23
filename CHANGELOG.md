# Changelog

## 0.4.1 - 2026-08-23

- Align repository, citation, and dataset-card authorship with the final manuscript.
- Reframe the project summary around the benchmark, role-aware diagnostics, and the
  observed composition-versus-selection result before release engineering.
- Clarify that both absent V2 validation rows originate in malformed HotpotQA source
  records, while clean-source omissions are confined to the incomplete training run.

## 0.4.0 - 2026-08-21

- Harden model-agnostic generation with bounded deterministic concurrency,
  per-record retry provenance, exclusive output locks, atomic reconciled error
  ledgers, explicit difficulty filtering, and nonzero incomplete-run status.
- Remove silent placeholder and source-copy translation fallbacks; retry invalid
  endpoint responses under the structured contract and retain typed failure origin.
- Replace the environment-specific judge runners with one credential-safe,
  OpenAI-compatible workflow using typed HotpotQA sources, strict JSON prompt v2,
  deterministic language-balanced sample manifests, resumable compact results,
  and prompt/model/sample provenance without hidden reasoning retention.
- Preserve exact versioned hashes for the historical judge prompts so previously
  generated V1/V2 judge artifacts remain documentable without reinterpreting them
  as outputs of the new prompt.
- Add RC1 release tooling for the source-complete `xhotpotqa_v1_1_audited`
  configuration, the corrective V2 artifact, and separately curated V1/V2 judge
  artifacts. V1.1 retains every ordered original English `source_sentences` array;
  release builders emit checksum-bearing manifests and do not imply publication.
- Remove ad-hoc generation/retry/judge scripts and environment-specific reports in
  favor of package CLI commands and tested release builders.

## 0.3.1 - 2026-08-13

- Upgrade the public dataset card with a responsive scientific visual hierarchy,
  compact release-state panels, role-aware benchmark anatomy, and verified-result cards.
- Use Hugging Face's documented KaTeX delimiters throughout the card and add a
  regression test that rejects non-rendering display or inline math syntax.
- Distinguish the 6,966-row non-quarantined sensitivity view from the stricter
  6,962-row accepted-only view in loading and reporting guidance.

## 0.3.0 - 2026-08-13

- Publish the audit-preserving `xhotpotqa_v1_audited` Parquet configuration on the Hugging
  Face Hub with 15,661 train rows, 7,405 validation rows, per-row structural status, and a
  checksum-bearing release manifest.

- Add deterministic, atomic construction of all 24 XHotpotQA+ question--answer views from
  canonical base records and source-ID keyed translations.
- Add `expand-plus`, strict canonical cardinality gates, JSON/JSONL input contracts, and
  integrity tests for fixed evidence, provenance, IDs, and checksums.
- Implement release support for the prospective XHotpotQA+ configuration, including
  streaming validation against the base data and an atomic four-file Hub release manifest;
  the incomplete parallel artifacts are not published.
- Add a streaming, checksum-pinned importer for the historical pandas-column shards, with
  content-addressed corrections, quarantine manifests, and strict ordered joins to HotpotQA.
- Version the evaluation normalization contract and add Unicode/script-aware answer scoring,
  script-relation summaries, mismatch/entropy bins, and an explicit no-distractor/NA stratum.
- Make V2 generation model-agnostic through a generic OpenAI-compatible configuration and
  vLLM serving script; retain the Gemma configuration only as an optional example.
- Finalize the pre-release V2 wire contract by embedding task-specific JSON response schemas
  in every translation request while retaining prompt version `xhotpotqa-translation-v2.0`.
- Add optional, checksum-pinned replay of V1 question--answer and paragraph language
  assignments for source/unit/language-paired corrective V2 audits.

## 0.2.0 - 2026-08-10

- Added a deterministic, resumable model-agnostic OpenAI-compatible generation pipeline,
  with a Gemma configuration retained only as an example.
- Added canonical JSONL validation and release gates.
- Added answer, support, joint, and language-mismatch evaluation.
- Added a Hugging Face dataset card and upload workflow.

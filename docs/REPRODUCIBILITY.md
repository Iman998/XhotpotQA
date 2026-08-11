# Reproducibility protocol

1. Pin the source HotpotQA release and record its SHA-256 checksum.
2. Filter only `hard` training examples; keep all 7,405 distractor validation examples.
3. Preserve the evaluated V1 assignment manifest and checksum. Use the versioned hash-based
   assigner and a published seed only for V2 or later regenerated releases.
4. Generate with the exact model ID, revision, prompt version, and decoding settings.
5. Resume by source ID; never reseed a shard.
6. Validate sentence cardinality, IDs, supporting indices, language codes, and checksums.
7. Run automatic language-ID, entity/number preservation, and answer-preservation checks.
8. Audit a stratified sample with bilingual annotators and adjudicate disagreements.
9. Freeze canonical JSONL files, publish the generated manifest, and tag the code commit.

For XHotpotQA+, freeze the canonical base split and the source-ID keyed question--answer
translation mapping independently. Run `expand-plus` only after both artifacts pass checksum
and language-inventory validation. The release preflight then verifies every expanded view
against its canonical base before publishing both configurations in one Hub commit. Views of
one source are correlated; evaluation confidence intervals over the parallel expansion should
therefore cluster by `source_id`.

The generation client is model-agnostic: `model_id`, `revision`, decoding, and optional
`chat_template_kwargs` are supplied by YAML. `configs/generation/openai_compatible.yaml` is
the neutral template; `configs/generation/gemma4_31b.yaml` is one model-specific example.
Production runs should preserve raw responses with `--audit-log` in a protected private path
but publish only parsed translations and provenance.

The client reads `OPENAI_BASE_URL` and `OPENAI_API_KEY` from the environment. For a local
unprotected endpoint, vLLM accepts a non-empty placeholder key; protected deployments must
obtain the key from a secret manager. The client refuses placeholder credentials for non-loopback
URLs. Tokens are never accepted as command-line arguments.

Before generation, replace placeholder or mutable revisions in the selected configuration and
server command with the same immutable checkpoint revision. A release provenance record is only
as precise as that resolved revision. Use `upload-hf --dry-run` with both base and XHotpotQA+ split pairs
to validate counts, checksums, derivation invariants, card metadata, and declared Hub paths
without reading credentials or contacting the Hub.

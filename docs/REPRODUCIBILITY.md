# Reproducibility protocol

1. Pin the source HotpotQA release and record its SHA-256 checksum.
2. Filter only `hard` training examples; keep all 7,405 distractor validation examples.
3. Assign languages with the versioned hash-based assigner and a published seed.
4. Generate with the exact model ID, revision, prompt version, and decoding settings.
5. Resume by source ID; never reseed a shard.
6. Validate sentence cardinality, IDs, supporting indices, language codes, and checksums.
7. Run automatic language-ID, entity/number preservation, and answer-preservation checks.
8. Audit a stratified sample with bilingual annotators and adjudicate disagreements.
9. Freeze JSONL and Parquet files, publish manifests, and tag the code commit.

For Gemma 4 31B, the reference recipe uses `google/gemma-4-31B-it` behind vLLM's
OpenAI-compatible endpoint, thinking disabled, and greedy decoding. Production runs should preserve
raw responses in a private audit log but publish only parsed translations and provenance.

The client reads `OPENAI_BASE_URL` and `OPENAI_API_KEY` from the environment. For a local
unprotected endpoint, vLLM accepts a non-empty placeholder key; protected deployments must
obtain the key from a secret manager. The client refuses placeholder credentials for non-loopback
URLs. Tokens are never accepted as command-line arguments.

Before generation, replace the mutable `main` model revision in the example configuration and
server command with the same immutable Hub commit. A release provenance record is only as precise
as that resolved revision. Use `upload-hf --dry-run` to validate split counts, checksums, card
metadata, and declared Hub paths without reading credentials or contacting the Hub.

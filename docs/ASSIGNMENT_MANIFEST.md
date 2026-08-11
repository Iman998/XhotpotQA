# Frozen language-assignment manifest

Corrective V2 regeneration can replay the evaluated V1 language conditions exactly instead
of assigning new languages. Pass a frozen JSON manifest to `generate-v2`:

```bash
xhotpotqa generate-v2 \
  --input data/raw/hotpot_dev_distractor_v1.json \
  --output data/processed/validation.v2.jsonl \
  --config configs/generation/openai_compatible.yaml \
  --split validation \
  --assignment-manifest data/manifests/v1.validation.assignments.json
```

The client remains model-agnostic. The manifest changes only the assignment strategy; model,
revision, prompt, decoding, and endpoint remain configuration concerns.

## JSON contract

```json
{
  "schema_version": "xhotpotqa-assignment-manifest-v1",
  "assignment_version": "xhotpotqa-v2-v1-assignment-replay-v1",
  "assignments": {
    "5a7a06935542990198eaf050": {
      "question-answer": "fa",
      "paragraph:0": "en",
      "paragraph:1": "de"
    }
  }
}
```

`assignments` is a mapping from immutable HotpotQA `source_id` to unit IDs and ISO 639-1
target-language codes. `question-answer` is one joint unit because the answer must use the
question language. Paragraph units are zero-based, contiguous, and named `paragraph:0`,
`paragraph:1`, and so on in source-context order.

Loading is strict: duplicate JSON keys, unknown root fields, unsupported language codes,
missing question--answer assignments, invalid unit names, and gaps in paragraph indices are
rejected. Immediately before any model request for a source, generation also checks that the
manifest's unit set exactly equals that source record's question--answer and paragraph units.
This catches both missing and surplus paragraph assignments before partial translation.

## Provenance and paired audit

Every generated record stores both the manifest-declared `assignment_version` and the SHA-256
of the exact manifest file bytes in `provenance.assignment_manifest_sha256`; manifest-backed
runs record `seed: null`. Resume is refused if either value differs from existing output.
Without `--assignment-manifest`, the existing `sha256-hash-v1` strategy and configured seed are
used exactly as before, and the manifest hash is empty.

The manifest defines stable paired-audit keys:

```text
(source_id, unit_id, target_language)
```

Join V1 and corrective V2 translations on that triple. For paragraphs, `unit_id` is the
source-order ID (`paragraph:N`), not a translated title or output paragraph ID. The file hash,
source-data hash, model revision, prompt hash, decoding parameters, and generated JSONL hash
should be frozen together in the release manifest.

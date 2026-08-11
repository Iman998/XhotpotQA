# Data directory

Large data files are intentionally excluded from Git. Place source HotpotQA files in
`data/raw/` and validated outputs in `data/processed/`. Public releases belong in the
Hugging Face dataset repository, not in Git history.

Recommended local names for the parallel expansion inputs and outputs are:

```text
data/processed/qa-translations.train.jsonl
data/processed/qa-translations.validation.jsonl
data/processed/xhotpotqa-plus.train.jsonl
data/processed/xhotpotqa-plus.validation.jsonl
```

The current publication payload prepared for the Hugging Face Hub uses the audited Parquet
configuration
`xhotpotqa_v1_audited` and the paths
`data/xhotpotqa_v1_audited/{train,validation}-*.parquet`. Its 15,661 training rows and
7,405 validation rows retain `status` and `structural_flags`; quarantined records remain in
the benchmark denominator. Rebuild that payload with `scripts/build_hf_public_v1.py` and
publish the reviewed dataset card as its repository-level `README.md`.

The JSONL names above belong to the prospective corrected canonical release. That future
release will expose `xhotpotqa` and the complete parallel expansion `xhotpotqa_plus` only
after all strict validation gates pass. Run the four-file `upload-hf --dry-run` preflight
before any networked canonical release.

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

The Hugging Face release publishes the canonical files as config `xhotpotqa` and the expanded
files as config `xhotpotqa_plus`. Run the four-file `upload-hf --dry-run` preflight before any
networked release.

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

The public [XHotpotQA dataset](https://huggingface.co/datasets/Iman998/XhotpotQA) recommends
the audited Parquet configuration `xhotpotqa_v1_1_audited` at frozen, loadable revision
`1d29e7918cf1acc045726c70fddba82371833090`. Its 15,661 training rows and 7,405 validation
rows retain `status` and `structural_flags`; quarantined records remain in the benchmark
denominator. V1.1 also stores every original English candidate title and ordered sentence
array as `source_title` and `source_sentences`. Rebuild that snapshot with
`scripts/build_hf_public_v1.py`; the reviewed `dataset_card/README.md` is the source for the
Hub repository-level card. The immutable earlier `xhotpotqa_v1_audited` configuration remains
available at revision `52b8bee41ff2bb0d41cd400ff5646c0e800b5127`.

The JSONL names above belong to the prospective corrected canonical release. That future
release will expose `xhotpotqa` and the complete parallel expansion `xhotpotqa_plus` only
after all strict validation gates pass. Run the four-file `upload-hf --dry-run` preflight
before any networked canonical release.

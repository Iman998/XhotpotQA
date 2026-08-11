---
pretty_name: XHotpotQA canonical release fixture
language:
- ar
- bn
- de
- el
- en
- es
- fa
- fr
- hi
- id
- it
- ja
- ko
- nl
- pl
- pt
- ru
- sv
- sw
- th
- tr
- ur
- vi
- zh
license: cc-by-sa-4.0
size_categories:
- 10K<n<100K
- 100K<n<1M
configs:
- config_name: xhotpotqa
  default: true
  data_files:
  - split: train
    path: data/xhotpotqa/train.jsonl
  - split: validation
    path: data/xhotpotqa/validation.jsonl
- config_name: xhotpotqa_plus
  data_files:
  - split: train
    path: data/xhotpotqa_plus/train.jsonl
  - split: validation
    path: data/xhotpotqa_plus/validation.jsonl
---

# Canonical release card fixture

This test-only fixture describes the prospective strict JSONL artifacts accepted by the
canonical Hub uploader. It is intentionally separate from the public audited-V1 Parquet card.

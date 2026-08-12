#!/usr/bin/env bash
set -uo pipefail

cd /data/Iman/dataset/hf_sft/xhotpot/XhotpotQA-main

export OPENAI_BASE_URL=http://192.168.1.204:16688/v1
export OPENAI_API_KEY=EMPTY
export PIP_CONFIG_FILE=/dev/null

PY=/opt/conda/bin/python
WORKERS=128
CFG=configs/generation/gemma4_31b_local.yaml

mkdir -p data/processed

echo "========================================================"
echo " XHotpotQA V2 generation — gemma-4-31B-it, ${WORKERS} threads, temp=0"
echo " start: $(date -Is)"
echo "========================================================"

# --- Validation split ---
echo ""
echo ">>> [1/2] VALIDATION split (7,405 records)"
"$PY" -m xhotpotqa generate-v2 \
  --input ../hotpot_dev_distractor_v1.json \
  --output data/processed/validation.v2.jsonl \
  --config "$CFG" \
  --split validation \
  --max-workers "$WORKERS"
echo "validation done: $(date -Is)"

# --- Train split (hard only) ---
echo ""
echo ">>> [2/2] TRAIN split (hard level, 15,661 records)"
"$PY" -m xhotpotqa generate-v2 \
  --input ../hotpot_train_v1.1.json \
  --output data/processed/train.v2.jsonl \
  --config "$CFG" \
  --split train \
  --max-workers "$WORKERS"
echo "train done: $(date -Is)"

echo ""
echo "========================================================"
echo " ALL DONE: $(date -Is)"
echo "========================================================"
echo "validation records: $(wc -l < data/processed/validation.v2.jsonl 2>/dev/null || echo 0)"
echo "train records:      $(wc -l < data/processed/train.v2.jsonl 2>/dev/null || echo 0)"
echo "validation errors:  $(wc -l < data/processed/validation.v2.jsonl.errors.jsonl 2>/dev/null || echo 0)"
echo "train errors:       $(wc -l < data/processed/train.v2.jsonl.errors.jsonl 2>/dev/null || echo 0)"

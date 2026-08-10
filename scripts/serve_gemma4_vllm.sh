#!/usr/bin/env bash
set -euo pipefail

: "${TENSOR_PARALLEL_SIZE:=4}"
: "${MAX_MODEL_LEN:=16384}"

exec vllm serve google/gemma-4-31B-it \
  --served-model-name google/gemma-4-31B-it \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --reasoning-parser gemma4 \
  --default-chat-template-kwargs '{"enable_thinking": false}'


#!/usr/bin/env bash
set -euo pipefail

: "${MODEL_ID:?Set MODEL_ID to the name exposed by the OpenAI-compatible endpoint}"
: "${CHECKPOINT:=${MODEL_ID}}"
: "${TENSOR_PARALLEL_SIZE:=1}"
: "${MAX_MODEL_LEN:=16384}"

exec vllm serve "${CHECKPOINT}" \
  --served-model-name "${MODEL_ID}" \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
  --max-model-len "${MAX_MODEL_LEN}"

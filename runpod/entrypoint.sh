#!/bin/bash
set -euo pipefail

if [ -z "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
  echo "ERROR: HUGGING_FACE_HUB_TOKEN is required (Hugging Face read token for Kyutai models)." >&2
  exit 1
fi

# Optional RunPod network volume: reuse model/token/cache state across Pod recreations.
# Mount the volume at /runpod-volume (or set RUNPOD_VOLUME_ROOT). Set RUNPOD_USE_VOLUME=0 to skip.
if [ "${RUNPOD_USE_VOLUME:-1}" != "0" ] && [ "${RUNPOD_USE_VOLUME:-}" != "false" ]; then
  VR="${RUNPOD_VOLUME_ROOT:-/runpod-volume}"
  if [ -d "$VR" ] && [ -w "$VR" ]; then
    mkdir -p \
      "${VR}/cache/huggingface" \
      "${VR}/cache/huggingface/transformers" \
      "${VR}/cache/torch" \
      "${VR}/cache/uv" \
      "${VR}/cache/xdg"
    export HF_HOME="${VR}/cache/huggingface"
    export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
    export TORCH_HOME="${VR}/cache/torch"
    export UV_CACHE_DIR="${VR}/cache/uv"
    export XDG_CACHE_HOME="${VR}/cache/xdg"
    echo "Using persistent caches on volume: HF_HOME=${HF_HOME}"
  else
    echo "Note: no writable volume at ${VR} (set RUNPOD_VOLUME_ROOT or mount /runpod-volume) — using container-local caches."
  fi
fi

# Persist HF credentials for Kyutai downloads inside STT/TTS processes.
export HF_TOKEN="${HUGGING_FACE_HUB_TOKEN}"
uvx --from 'huggingface_hub[cli]' hf auth login --token "${HUGGING_FACE_HUB_TOKEN}"

# Defaults match speak2 Inception Mercury preset (override via RunPod env).
export KYUTAI_STT_URL="${KYUTAI_STT_URL:-ws://127.0.0.1:8091}"
export KYUTAI_TTS_URL="${KYUTAI_TTS_URL:-ws://127.0.0.1:8092}"
export KYUTAI_LLM_URL="${KYUTAI_LLM_URL:-https://api.inceptionlabs.ai}"
export KYUTAI_LLM_MODEL="${KYUTAI_LLM_MODEL:-mercury-2}"

if [ -z "${KYUTAI_LLM_API_KEY:-}" ]; then
  echo "WARNING: KYUTAI_LLM_API_KEY is empty — external LLM calls will fail until set." >&2
fi

exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf

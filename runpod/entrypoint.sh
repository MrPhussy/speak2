#!/bin/bash
set -euo pipefail

if [ -z "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
  echo "ERROR: HUGGING_FACE_HUB_TOKEN is required (Hugging Face read token for Kyutai models)." >&2
  exit 1
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

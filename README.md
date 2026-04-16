# speak2: Unmute + Gemma 4 E2B (RunPod-oriented)

This directory vendors [kyutai-labs/unmute](https://github.com/kyutai-labs/unmute) as a **git submodule** under `unmute/` and adds **Docker Compose overrides** for:

- **Single GPU**: Kyutai STT + Kyutai TTS + vLLM `google/gemma-4-E2B-it` on one machine (tight VRAM; see below).
- **Split LLM**: STT + TTS + backend + frontend on one deployment, while the LLM runs on another host (self-hosted vLLM, second RunPod, etc.).
- **External LLM (Inception Mercury 2)**: same as split (no local `llm` container); backend calls [Inception’s OpenAI-compatible API](https://docs.inceptionlabs.ai/get-started/get-started) ([Mercury 2 announcement](https://www.inceptionlabs.ai/blog/introducing-mercury-2)).

Canonical path on this machine: **`/home/phil/workspace/speak2`**. If you use `/workspace/speak2` in docs or CI, create a symlink (requires a writable `/workspace`):

```bash
sudo mkdir -p /workspace && sudo ln -sfn /home/phil/workspace/speak2 /workspace/speak2
```

## Prerequisites

- **x86_64 Linux** with NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
- **VRAM**: With an **external** LLM (Inception Mercury, OpenAI, OpenRouter, etc.), the GPU only runs **Kyutai STT + TTS** (order-of-magnitude **~8GB+** VRAM combined—use **16GB+** for comfort). With **local Gemma 4 E2B**, Unmute’s single-GPU target is tighter (**32GB+** practical). Always confirm with `nvidia-smi` under load.
- **Hugging Face**: Accept model license(s) on the HF hub and set `HUGGING_FACE_HUB_TOKEN` (read-only token for deployment).

## Layout

| Path | Purpose |
|------|---------|
| [`unmute/`](unmute/) | Submodule: upstream Unmute |
| [`compose/docker-compose.runpod.single-gpu.yml`](compose/docker-compose.runpod.single-gpu.yml) | Override: `vllm/vllm-openai:gemma4`, Gemma 4 E2B-it, text-only limits |
| [`compose/docker-compose.runpod.split-llm.yml`](compose/docker-compose.runpod.split-llm.yml) | Override: disable local `llm` by default; set `KYUTAI_LLM_URL` / model / API key for any external OpenAI-compatible host |
| [`compose/docker-compose.runpod.inception-mercury.yml`](compose/docker-compose.runpod.inception-mercury.yml) | Same, with defaults for **Inception** `https://api.inceptionlabs.ai` + model `mercury-2` |
| [`env.example`](env.example) | Copy to `.env` |

## Quick start (single GPU)

From **this directory** (`speak2` root):

```bash
cp env.example .env
# edit .env — set HUGGING_FACE_HUB_TOKEN at minimum

docker compose -f unmute/docker-compose.yml -f compose/docker-compose.runpod.single-gpu.yml --env-file .env up --build
```

Open **port 80** on the host (Traefik). For local port mapping without editing upstream, use SSH port forward as in the Unmute README, or add a small override that publishes `80:80` (already default).

### Tuning single-GPU vLLM

Edit [`compose/docker-compose.runpod.single-gpu.yml`](compose/docker-compose.runpod.single-gpu.yml):

- **`--max-model-len`**: lower if you OOM (KV cache).
- **`--gpu-memory-utilization`**: balance against STT+TTS; raise only if LLM has spare VRAM.
- After stability, consider **`--async-scheduling`** (vLLM Gemma 4 docs) for throughput—add only after smoke tests pass.

For production, **pin the vLLM image by digest** after a successful pull (`docker inspect --format='{{index .RepoDigests 0}}' vllm/vllm-openai:gemma4`).

## RunPod: voice stack + external LLM (Inception Mercury 2)

Use this when the LLM is **not** on the pod—only **Traefik + frontend + backend + STT + TTS** need a GPU (for Kyutai).

1. Copy [`env.example`](env.example) to `.env` and set:
   - `HUGGING_FACE_HUB_TOKEN` (Kyutai / HF)
   - `KYUTAI_LLM_API_KEY` — your **Inception API key** from [API Keys](https://platform.inceptionlabs.ai/dashboard/api-keys) (see [Get started](https://docs.inceptionlabs.ai/get-started/get-started))
2. Ensure `KYUTAI_LLM_URL` is **`https://api.inceptionlabs.ai`** with **no `/v1` suffix** (Unmute adds `/v1` when talking to the OpenAI client).
3. Start:

```bash
docker compose -f unmute/docker-compose.yml -f compose/docker-compose.runpod.inception-mercury.yml --env-file .env up --build
```

Defaults in that override: `KYUTAI_LLM_MODEL=mercury-2`, `KYUTAI_LLM_URL=https://api.inceptionlabs.ai`. Override in `.env` if Inception changes the hostname or model id.

**Mercury-only note:** Inception supports extra fields such as `reasoning_effort` for latency vs quality ([docs](https://docs.inceptionlabs.ai/get-started/get-started)). Stock Unmute only sends `model`, `messages`, `stream`, and `temperature` in `chat.completions.create` ([`unmute/unmute/llm/llm_utils.py`](unmute/unmute/llm/llm_utils.py)), so you get provider defaults until you patch Unmute or wrap the API.

**RunPod checklist**

- **HTTP(S)**: expose the pod **TCP port 80** (Traefik). For HTTPS and browser microphone access, terminate TLS in front of the pod (RunPod proxy, Caddy, nginx, etc.); plain HTTP only works cleanly for **localhost** in most browsers.
- **Outbound**: the backend container must reach **`https://api.inceptionlabs.ai`** (egress allowed).
- **Region**: pick a data center with stable egress; latency to Inception adds to **time-to-first-token** after STT.

## Split topology (LLM on a second RunPod — self-hosted vLLM)

1. **LLM pod**: run vLLM with the same model flags (image `vllm/vllm-openai:gemma4`, `google/gemma-4-E2B-it`, text-only limits). Expose port **8000** (or behind TLS termination).
2. **Voice pod**: from `speak2` root, set the LLM base URL (no `/v1` suffix—the backend appends `/v1`):

```bash
export KYUTAI_LLM_URL=http://REPLACE_WITH_VLLM_HOST:8000
docker compose -f unmute/docker-compose.yml -f compose/docker-compose.runpod.split-llm.yml --env-file .env up --build
```

The merged compose **does not start** the `llm` service unless you explicitly enable the unused profile (you should not for this topology):

```bash
# not needed for split — shown only for clarity
docker compose ... --profile speak2-local-llm up   # would start bundled vLLM; omit for split
```

### RunPod networking

- Place both pods in the **same region** to keep RTT low.
- Use RunPod **pod networking / global networking** where applicable so the voice backend reaches vLLM on **private** addresses instead of routing over the public internet. See [RunPod networking documentation](https://docs.runpod.io/pods/networking).
- Default Unmute compose is **HTTP**. For browsers and microphones you need **HTTPS** in production; options include terminating TLS in front of Traefik (Caddy/nginx) or adapting patterns from Unmute’s Swarm docs.

## Updating the Unmute submodule

```bash
git submodule update --remote --merge unmute
```

## Latency checks

Inside the submodule, Unmute ships a WebSocket load client:

```bash
cd unmute
uv run unmute/loadtest/loadtest_client.py --server-url ws://YOUR_HOST:MAPPED_PORT --n-workers 4
```

(Adjust URL to match how you expose the backend; the default compose fronts Traefik on port 80.)

## Relation to Gemma 4 + TADA (TensorRT)

Your fused TensorRT-LLM + TADA acoustic server (`native-gemma-tada` / `serve_gemma4_tada.py`) is **not** a drop-in replacement for Kyutai TTS in stock Unmute. Keeping Unmute’s **Kyutai STT + Kyutai TTS** with **Gemma 4 E2B as the text LLM** is the supported configuration here. Replacing LLM+TTS with a fused server would require a **custom adapter** for Unmute’s WebSocket TTS protocol.

## Troubleshooting

### Backend image build: `audiopus_sys` / CMake / Opus

If `uv run` during the backend image build fails while compiling `sphn` with errors about **`audiopus_sys`** or **CMake < 3.5**, the Unmute `Dockerfile` in this submodule installs **`libopus-dev`** and **`pkg-config`** so the crate links system Opus instead of building an old bundled copy. The same dependency is added to **`services/moshi-server/public.Dockerfile`** so **STT/TTS** (`moshi-server`) does not hit the same failure at runtime. Rebuild with a clean cache if needed: `docker compose ... build --no-cache backend stt tts`.

### STT/TTS exit immediately: `huggingface-cli` deprecated

If `stt` / `tts` logs say **`huggingface-cli` is deprecated** and **`Use hf instead`**, the moshi startup scripts in this submodule were updated to run **`hf auth login --token …`** via `uvx`. Rebuild **`stt`** and **`tts`**: `docker compose ... build --no-cache stt tts`.

### Traefik: `client version 1.24 is too old` (Docker API 1.44)

Docker Engine 29+ requires API **1.44+**. Traefik **v3.3.x** used an older client. This repo’s submodule pins **`traefik:v3.6.6`**, which negotiates a compatible API. Re-pull after `git submodule update`: `docker compose ... pull traefik`.

## References

- [kyutai-labs/unmute](https://github.com/kyutai-labs/unmute)
- [Inception Mercury 2](https://www.inceptionlabs.ai/blog/introducing-mercury-2) · [Inception API get started](https://docs.inceptionlabs.ai/get-started/get-started)
- [google/gemma-4-E2B-it](https://huggingface.co/google/gemma-4-E2B-it)
- [vLLM Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md)

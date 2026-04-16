# speak2: Unmute + Gemma 4 E2B (RunPod-oriented)

This directory vendors [kyutai-labs/unmute](https://github.com/kyutai-labs/unmute) as a **git submodule** under `unmute/` and adds **Docker Compose overrides** for:

- **Single GPU**: Kyutai STT + Kyutai TTS + vLLM `google/gemma-4-E2B-it` on one machine (tight VRAM; see below).
- **Split LLM**: STT + TTS + backend + frontend on one deployment, while the LLM runs on another host (recommended when you want a full GPU for vLLM).

Canonical path on this machine: **`/home/phil/workspace/speak2`**. If you use `/workspace/speak2` in docs or CI, create a symlink (requires a writable `/workspace`):

```bash
sudo mkdir -p /workspace && sudo ln -sfn /home/phil/workspace/speak2 /workspace/speak2
```

## Prerequisites

- **x86_64 Linux** with NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
- **VRAM**: Unmute’s default **Gemma 3 1B** stack targets **16GB**. Gemma 4 E2B in vLLM is documented as **24GB+** when multimodal features are enabled; this stack uses **`--limit-mm-per-prompt image=0,audio=0`** (text-only LLM; audio still goes through Kyutai STT) to shrink the footprint. **Practical single-GPU target: 32GB+** (e.g. RTX 4090/5090 class). Always confirm with `nvidia-smi` under load.
- **Hugging Face**: Accept model license(s) on the HF hub and set `HUGGING_FACE_HUB_TOKEN` (read-only token for deployment).

## Layout

| Path | Purpose |
|------|---------|
| [`unmute/`](unmute/) | Submodule: upstream Unmute |
| [`compose/docker-compose.runpod.single-gpu.yml`](compose/docker-compose.runpod.single-gpu.yml) | Override: `vllm/vllm-openai:gemma4`, Gemma 4 E2B-it, text-only limits |
| [`compose/docker-compose.runpod.split-llm.yml`](compose/docker-compose.runpod.split-llm.yml) | Override: disable local `llm` by default; backend uses `KYUTAI_LLM_URL` |
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

## Split topology (LLM on a second RunPod)

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

If `uv run` during the backend image build fails while compiling `sphn` with errors about **`audiopus_sys`** or **CMake < 3.5**, the Unmute `Dockerfile` in this submodule installs **`libopus-dev`** and **`pkg-config`** so the crate links system Opus instead of building an old bundled copy. Rebuild with a clean cache if needed: `docker compose ... build --no-cache backend`.

## References

- [kyutai-labs/unmute](https://github.com/kyutai-labs/unmute)
- [google/gemma-4-E2B-it](https://huggingface.co/google/gemma-4-E2B-it)
- [vLLM Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md)

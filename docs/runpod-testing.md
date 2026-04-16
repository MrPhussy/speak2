# Deploying speak2 / Unmute on RunPod

RunPod **Pods** are **one container per deployment**. Official docs state you **cannot** run your own Docker daemon or **Docker Compose** inside a Pod ([Pod limitations — *Docker Compose is not supported*](https://docs.runpod.io/pods/overview)).

The multi-file Compose flow under `compose/` is for **Docker hosts** (e.g. DGX Spark). For **RunPod Pods**, use the **single all-in-one image** in this repo.

---

## Single image (default for RunPod)

[`Dockerfile.runpod-allinone`](../Dockerfile.runpod-allinone) bundles:

- **Traefik** (file provider — no Docker socket) on **:80**
- **Next.js** frontend (production `standalone` build) on **:3000** (internal)
- **Unmute FastAPI** backend on **:8088** (internal)
- **Kyutai STT** (`moshi-server`) on **:8091** (internal)
- **Kyutai TTS** on **:8092** (internal)

Process manager: **supervisord** ([`runpod/supervisord.conf`](../runpod/supervisord.conf)). Entrypoint: [`runpod/entrypoint.sh`](../runpod/entrypoint.sh) (HF login + env defaults for Inception Mercury).

### Build and push

From the **speak2** repo root (with `unmute/` submodule populated):

```bash
docker build -f Dockerfile.runpod-allinone -t YOUR_REGISTRY/speak2-unmute:runpod .
docker push YOUR_REGISTRY/speak2-unmute:runpod
```

Use a registry RunPod can pull from (Docker Hub, GHCR, ECR, etc.).

### RunPod Pod (test today)

1. [Deploy a Pod](https://docs.runpod.io/pods/overview) with image `YOUR_REGISTRY/speak2-unmute:runpod`, **GPU** (16GB+ VRAM recommended for STT+TTS), and **HTTP or TCP** exposure on container port **80**.
2. Set **environment variables** (Pod → Edit → Environment):

| Name | Example | Required |
|------|---------|----------|
| `HUGGING_FACE_HUB_TOKEN` | `hf_…` | Yes |
| `KYUTAI_LLM_API_KEY` | Inception key | Yes for Mercury |
| `KYUTAI_LLM_URL` | `https://api.inceptionlabs.ai` | Optional (default) |
| `KYUTAI_LLM_MODEL` | `mercury-2` | Optional (default) |
| `KYUTAI_STT_URL` | `ws://127.0.0.1:8091` | Optional (default) |
| `KYUTAI_TTS_URL` | `ws://127.0.0.1:8092` | Optional (default) |
| `UV_LINK_MODE` | `copy` | Optional (helps some volume backends) |
| `RUNPOD_VOLUME_ROOT` | `/runpod-volume` | Optional; base path for persistent caches (default if that directory exists) |
| `RUNPOD_USE_VOLUME` | `0` or `false` | Optional; disable volume-backed caches even if `/runpod-volume` exists |

**Network volume (reuse state):** Mount a RunPod network volume at **`/runpod-volume`**. On startup, [`runpod/entrypoint.sh`](../runpod/entrypoint.sh) sets `HF_HOME`, `TORCH_HOME`, `UV_CACHE_DIR`, and `XDG_CACHE_HOME` under `${RUNPOD_VOLUME_ROOT:-/runpod-volume}/cache/…` so Hugging Face models, tokens, and related caches survive new Pods using the same volume.

3. **Expose port 80** so Traefik is reachable:
   - **TCP** exposure is preferred for **long-lived WebSockets** ([RunPod expose ports](https://docs.runpod.io/pods/configuration/expose-ports)); use the public **IP:port** from **Connect → Direct TCP Ports** and open `http://IP:PORT/` in the browser (mic may still want HTTPS — see below).
   - **HTTP proxy** (`https://[POD_ID]-80.proxy.runpod.net`) gives HTTPS but has a **~100s** Cloudflare timeout path; try it for quick UI tests, fall back to **TCP** if WebSockets drop.

4. Wait for **first boot**: Kyutai may download models on first STT/TTS start (several minutes). Watch **Logs** until Traefik answers on `/`.

5. **Healthcheck**: image `HEALTHCHECK` curls `http://127.0.0.1:80/`; allow several minutes before the Pod shows healthy.

### RunPod Serverless (later)

Serverless workers are still **one container** per worker; this image is compatible **in principle** once you validate on a Pod. You will likely need a **load-balancing** or **custom HTTP** endpoint type, correct **idle/execution timeouts**, and possibly a wrapper if RunPod expects a specific `CMD` — adapt after Pod testing. See [Serverless overview](https://docs.runpod.io/serverless/overview).

### Asterisk / FreePBX (later)

RunPod Pods **do not support UDP** ([Pod limitations](https://docs.runpod.io/pods/overview)). SIP/RTP toward Asterisk usually needs **UDP** or a **gateway** outside RunPod (e.g. Kamailio, cloud SBC, or TCP/TLS SIP). Plan telephony as a **separate** network hop from this HTTP/WebSocket voice UI.

---

## Option — Compose on a non-RunPod Docker host

Use `docker compose -f unmute/docker-compose.yml -f compose/docker-compose.runpod.inception-mercury.yml` on any Linux machine with Docker + NVIDIA (e.g. Spark). Same stack, different hosting model.

---

## Option — dockerless (manual, one container)

Upstream [Unmute without Docker](https://github.com/kyutai-labs/unmute#running-without-docker). Possible on a Pod via SSH if you install all deps yourself; ports differ from the all-in-one image — use only if you are debugging outside the Dockerfile.

---

## Networking reference

- **Bind** services on `0.0.0.0` (this image does).
- **WebSockets**: prefer **TCP** exposure when sessions are long ([RunPod guidance](https://docs.runpod.io/pods/configuration/expose-ports#common-use-cases)).
- **Egress**: backend must reach your LLM host (e.g. `https://api.inceptionlabs.ai`).

---

## Summary

| Approach | RunPod Pod |
|----------|------------|
| `docker compose …` | **Not supported** inside Pod |
| **`Dockerfile.runpod-allinone`** | **Yes** (this repo) |
| dockerless by hand | **Yes** (manual) |

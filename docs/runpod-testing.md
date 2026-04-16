# Deploying speak2 / Unmute on RunPod for testing

RunPod **Pods** are **one container per deployment**. Official docs state you **cannot** run your own Docker daemon or **Docker Compose** inside a Pod ([Pod limitations — *Docker Compose is not supported*](https://docs.runpod.io/pods/overview)).

So the **same** `docker compose -f unmute/docker-compose.yml -f compose/...` flow you use on Spark or a dev box is **not** something you paste into a standard RunPod Pod start command.

Below are **workable** ways to get “functional on RunPod” for testing, in order of practicality.

---

## Option 1 — Keep Compose off RunPod (simplest)

- Run the **full stack** (Compose + Inception override) on **any Linux host with Docker + NVIDIA** (e.g. your DGX Spark, a dev machine, or a **GPU VM** from a provider that gives you a real VM with Docker).
- Use RunPod only for **GPU inference** later (e.g. a separate endpoint), if that fits your product split.

This avoids fighting the single-container model.

---

## Option 2 — RunPod Pod + **one** custom image (recommended if the UI must be on RunPod)

Package **Traefik + frontend + backend + STT + TTS** into **one** Docker image with a process supervisor (`supervisord`, `s6-overlay`, or a small `bash` launcher that starts all processes and `wait`).

- **Build** on CI or locally: `docker build -t ghcr.io/yourorg/speak2-voice:tag -f Dockerfile.runpod-allinone .`
- **Push** to GHCR / Docker Hub.
- In [RunPod console](https://www.console.runpod.io/pods), deploy a Pod with that image, GPU type (**16GB+** VRAM for STT+TTS is a reasonable test floor), and environment variables (see below).

This repo **does not** ship `Dockerfile.runpod-allinone` yet; it is the straightforward way to align with RunPod’s model.

---

## Option 3 — RunPod Pod + **dockerless** (no Docker; one container, many processes)

Upstream Unmute documents [running without Docker](https://github.com/kyutai-labs/unmute#running-without-docker): `uv`, `cargo`, `pnpm`, CUDA, then `./dockerless/start_*.sh` in separate terminals.

On a RunPod Pod you can **SSH** in and run the same **if** your template has CUDA, build tools, and HF auth configured. You must:

- Install dependencies per Unmute README (Linux/WSL path).
- Export the same env vars you use in `.env` (`HUGGING_FACE_HUB_TOKEN`, `KYUTAI_LLM_*`, etc.).
- Point the **frontend** at the **backend** URL users will actually open (RunPod proxy/TCP — see below).
- **Skip** `start_llm.sh` when using Inception: set `KYUTAI_LLM_URL` / `KYUTAI_LLM_MODEL` / `KYUTAI_LLM_API_KEY` for the backend process.

**Caveat:** dockerless defaults (ports, no Traefik) differ from Compose; you will align ports and reverse-proxy yourself. This is viable for a **manual** test, not a one-click template, unless you script it.

---

## Networking on RunPod (important for Unmute)

### WebSockets and timeouts

Unmute relies on **WebSockets** (browser ↔ backend, backend ↔ STT/TTS). RunPod’s **HTTP proxy** terminates through Cloudflare with a **~100 second** timeout on slow responses ([proxy limitations](https://docs.runpod.io/pods/configuration/expose-ports#proxy-limitations-and-behavior)). Long silent periods or very slow first bytes can cause **524**-class issues.

RunPod recommends **TCP port exposure** for **WebSocket** workloads that need persistent connections ([WebSocket applications](https://docs.runpod.io/pods/configuration/expose-ports#common-use-cases)).

**Practical test setup:**

1. In the Pod / template, enable **Expose TCP Ports** and map to the port your **edge** listens on (with Compose that is usually **80** for Traefik, or **8000** if you only expose the backend in a custom image).
2. Use the **public IP:port** from the Pod **Connect** panel ([TCP access](https://docs.runpod.io/pods/configuration/expose-ports#tcp-access-via-public-ip)).
3. For **HTTPS** in the browser (needed for **microphone** access on non-localhost), the HTTP proxy gives you `https://[POD_ID]-[PORT].proxy.runpod.net` — test whether your WebSocket path stays under proxy limits; if not, terminate TLS yourself on TCP or use a small external reverse proxy.

### Bind address

Anything you expose must listen on **`0.0.0.0`**, not `127.0.0.1` ([RunPod troubleshooting](https://docs.runpod.io/pods/configuration/expose-ports#troubleshooting)).

---

## Environment variables on RunPod

Set in the Pod / template UI (or template env), mirroring your `.env`:

| Variable | Purpose |
|----------|---------|
| `HUGGING_FACE_HUB_TOKEN` | HF read token for Kyutai model download |
| `KYUTAI_LLM_API_KEY` | Inception (or other) API key |
| `KYUTAI_LLM_URL` | For Inception: `https://api.inceptionlabs.ai` (**no** `/v1`) |
| `KYUTAI_LLM_MODEL` | e.g. `mercury-2` |
| `NEWSAPI_API_KEY` | Optional |

Never commit real keys; use RunPod secrets / env UI only.

---

## Egress

The **backend** container (or process) must reach **`https://api.inceptionlabs.ai`** for Mercury. RunPod Pods normally allow HTTPS egress; if something fails, check firewall / template restrictions.

---

## Summary

| Approach | Fits RunPod Pod? |
|----------|------------------|
| `docker compose …` (current speak2 flow) | **No** (not supported on Pods) |
| Single custom image + supervisor | **Yes** |
| dockerless + SSH + manual processes | **Yes** (manual) |
| GPU VM elsewhere + Compose | **Yes** |

If you want **Option 2** implemented in-repo (`Dockerfile.runpod-allinone` + build instructions), say so in Agent mode and we can add it incrementally.

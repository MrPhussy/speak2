# VEXYL: dynamic S2S Gateway vs CASCADE (Unmute)

Use this together with:

- SpacetimeDB [`contrib/call-routing-core`](../contrib/call-routing-core) (DID → `S2S_GATEWAY` | `CASCADE`; see [`docs/CALL_ROUTING_SPACETIME.md`](CALL_ROUTING_SPACETIME.md))
- Asterisk example: [`deploy/asterisk/extensions_custom_fjord_parallel_test.conf.example`](../deploy/asterisk/extensions_custom_fjord_parallel_test.conf.example)
- RunPod Unmute image: [`Dockerfile.runpod-allinone`](../Dockerfile.runpod-allinone), [`docs/runpod-testing.md`](runpod-testing.md)

## Runtime

| Env | Purpose |
|-----|---------|
| `MODE=DYNAMIC` | VEXYL switches behavior per call using DID / SpacetimeDB / `AGENT_MODE` |
| `CASCADE_UNMUTE_BASE_URL` | Public base URL for the RunPod Pod (Traefik), e.g. `http://IP:PORT` — no trailing slash |
| `XAI_REALTIME_URL` | xAI Realtime WebSocket base (e.g. `wss://eu-west-1.api.x.ai/v1/realtime`) |
| `XAI_API_KEY` | xAI credentials for S2S Gateway leg |
| `SPACETIME_CALL_ROUTING_DB` | Database name/identity for published `call-routing-core` module |

## S2S Gateway (DID …111)

On connect, send **`session.update`** per your product spec, for example:

- `voice`: `ara`
- `instructions`: British assistant / full-duplex rules
- `input_audio_format` / `output_audio_format`: `g711_alaw`
- `turn_detection`: `server_vad` with desired `threshold`, `prefix_padding_ms`, `silence_duration_ms`
- `tools`: `{ "type": "web_search" }` if supported

Resolve PSTN codec negotiation with your carrier; align Asterisk audio path with `g711_alaw` as required.

## CASCADE (DID …222)

Point the media/control plane at **Unmute** behind Traefik on container **:80** (see [`unmute/docs/browser_backend_communication.md`](../unmute/docs/browser_backend_communication.md)). This is **not** Speak Metis **`/v1/ws`** unless you intentionally deploy [`workspace/speak/docker/Dockerfile.runpod-cleans2s-blackwell`](../../speak/docker/Dockerfile.runpod-cleans2s-blackwell) instead.

## Flow

1. Asterisk sets `AGENT_MODE` and bridges RTP to VEXYL AudioSocket.
2. VEXYL reads DID + optional SpacetimeDB `resolve_incoming_call`.
3. **S2S_GATEWAY** → xAI Realtime. **CASCADE** → Unmute URL.

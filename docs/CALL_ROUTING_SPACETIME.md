# Call routing (SpacetimeDB + VEXYL)

Rust module (WASM `cdylib`): [`contrib/call-routing-core`](../contrib/call-routing-core). Same source as the mneme crate; versioned here so it ships with **speak2**.

## Build

```bash
cd contrib/call-routing-core
spacetime build
```

If `rustc` is older than a transitive crate expects, pin with e.g. `cargo update -p constant_time_eq --precise 0.4.2` (a `Cargo.lock` is included for reproducibility).

## Publish

```bash
cd contrib/call-routing-core
spacetime publish call-routing --module-path . -y
```

Then call reducers from your client:

| Reducer | Purpose |
|--------|---------|
| `seed_fjord_demo_routes` | Inserts demo DIDs `442030000111` → **S2S_GATEWAY**, `442030000222` → **CASCADE** |
| `upsert_call_route` | Admin: set `did`, `mode`, `tenant_id` |
| `delete_call_route` | Remove a DID row |
| `resolve_incoming_call` | At call start: `call_id`, `dialed_number`—appends to **`incoming_call_resolution`** |

Subscribe to **`incoming_call_resolution`** from the Speak dashboard (`app.speak.ad`) to compare modes.

## Seed from CLI

```bash
export SPACETIME_URL=http://127.0.0.1:3000
export CALL_ROUTING_DB=call-routing
./scripts/seed_call_routing_demo.sh
```

## Modes

- **`S2S_GATEWAY`** — VEXYL uses **xAI Realtime** (`session.update`, `g711_alaw`, etc.); no Unmute container on that leg.
- **`CASCADE`** — VEXYL uses the **Unmute** stack (Traefik `:80` on RunPod) or **Speak CleanS2S** Metis if you point it there instead.

Normalize **`dialed_number`** consistently between Asterisk (E.164 vs national) and this table’s **`did`** keys.

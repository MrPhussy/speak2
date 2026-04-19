//! SpacetimeDB module: map **DID** (dialed number) to **`S2S_GATEWAY`** or **`CASCADE`** for VEXYL.
//!
//! Publish to a dedicated database (e.g. `call-routing`) and have VEXYL (or mneme-engine) call
//! [`resolve_incoming_call`] at session start. Subscribe to [`incoming_call_resolution`] for metrics.
//!
//! See [`docs/CALL_ROUTING_SPACETIME.md`](../../../docs/CALL_ROUTING_SPACETIME.md) in this repo.

use spacetimedb::{ReducerContext, Table};

pub const MODE_S2S_GATEWAY: &str = "S2S_GATEWAY";
pub const MODE_CASCADE: &str = "CASCADE";

#[spacetimedb::table(
    accessor = call_routing,
    name = "call_routing",
    public,
    index(accessor = by_tenant_id, btree(columns = [tenant_id]))
)]
pub struct CallRouting {
    #[primary_key]
    pub did: String,
    /// `S2S_GATEWAY` (xAI Realtime) or `CASCADE` (Unmute / Metis pipeline).
    pub mode: String,
    pub tenant_id: u32,
}

/// Append-only log so dashboards (e.g. app.speak.ad) can compare modes side-by-side.
#[spacetimedb::table(
    accessor = incoming_call_resolution,
    name = "incoming_call_resolution",
    public,
    index(accessor = by_call_id, btree(columns = [call_id])),
    index(accessor = by_dialed, btree(columns = [dialed_number]))
)]
pub struct IncomingCallResolution {
    #[primary_key]
    #[auto_inc]
    pub resolution_id: u64,
    pub call_id: String,
    pub dialed_number: String,
    pub mode: String,
    pub tenant_id: u32,
    pub resolved_ok: bool,
    pub detail: String,
    pub created_at: u64,
}

fn upsert_route_row(ctx: &ReducerContext, did: String, mode: String, tenant_id: u32) {
    let row = CallRouting {
        did: did.clone(),
        mode,
        tenant_id,
    };
    if ctx.db.call_routing().did().find(&did).is_some() {
        ctx.db.call_routing().did().update(row);
    } else {
        ctx.db.call_routing().insert(row);
    }
}

#[spacetimedb::reducer]
pub fn upsert_call_route(ctx: &ReducerContext, did: String, mode: String, tenant_id: u32) {
    upsert_route_row(ctx, did, mode, tenant_id);
}

#[spacetimedb::reducer]
pub fn delete_call_route(ctx: &ReducerContext, did: String) {
    ctx.db.call_routing().did().delete(did);
}

/// Idempotent demo seeds for parallel testing (replace DIDs with your live numbers).
#[spacetimedb::reducer]
pub fn seed_fjord_demo_routes(ctx: &ReducerContext) {
    upsert_route_row(
        ctx,
        "442030000111".into(),
        MODE_S2S_GATEWAY.into(),
        1,
    );
    upsert_route_row(
        ctx,
        "442030000222".into(),
        MODE_CASCADE.into(),
        1,
    );
}

/// VEXYL (or a telephony bridge) invokes this when a call arrives.
#[spacetimedb::reducer]
pub fn resolve_incoming_call(ctx: &ReducerContext, call_id: String, dialed_number: String) {
    let now = (ctx.timestamp.to_micros_since_unix_epoch() / 1_000_000) as u64;
    match ctx.db.call_routing().did().find(&dialed_number) {
        Some(route) => {
            ctx.db.incoming_call_resolution().insert(IncomingCallResolution {
                resolution_id: 0,
                call_id: call_id.clone(),
                dialed_number: dialed_number.clone(),
                mode: route.mode.clone(),
                tenant_id: route.tenant_id,
                resolved_ok: true,
                detail: String::new(),
                created_at: now,
            });
        }
        None => {
            ctx.db.incoming_call_resolution().insert(IncomingCallResolution {
                resolution_id: 0,
                call_id: call_id.clone(),
                dialed_number: dialed_number.clone(),
                mode: String::new(),
                tenant_id: 0,
                resolved_ok: false,
                detail: "DID not found in call_routing".into(),
                created_at: now,
            });
        }
    }
}

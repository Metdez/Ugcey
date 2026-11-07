# 04-01 Glasshand edge: SUMMARY

## Files created
- worker/glasshand/{types,oauth,store,core,allow,egress,relay,routes}.ts
- worker/test/glasshand.test.ts (11 tests)

## Files edited
- worker/index.ts: `app.route("/api/glasshand", glasshand)` after `requireKey` (covered by the `/api/*` gate) and before the container proxy.
- worker/do/agent-runtime.ts: `glasshand` table via `sqlStore`; RPC methods glasshandConnect/Status/Select/Disconnect/State/Token(stale?). The container env no longer reads GLASSHAND_TOKEN; `UGECY_HAS_GLASSHAND` is always "true" (the live check is `_ugecy/status`).
- worker/egress/vendors.ts: `glasshand.internal` is delegated to `handleGlasshand`; `VENDORS` keeps an `allowed(path, method)` entry (the existing edge test still passes). `handleVendor` now takes `props`.
- worker/egress/gateway.ts: passes `ctx.props`.

## Design
- `Glasshand` (core.ts) holds the state machine over a `GlasshandStore` (SQLite `glasshand(k,v)` or memory) with injectable fetch/clock. Mutations go through a promise-chain lock. `token(stale?)` refreshes at < 60 s remaining. Passing the token that just got a 401 refreshes only if it is still current, so concurrent callers share one rotation. Both tokens are written in one `transactionSync`. A rejected refresh (400/401/403) clears the tokens, and `token()` returns null. A transient failure throws.
- Status polling is persisted via `last_poll_at` and capped at one poll per interval. `slow_down` adds 5 s to the interval. `denied` and `expired` clear the pending fields.
- Relay: `fetch(controlUrl as https, {Upgrade, Authorization})`, `webSocket.accept()`, paired with a `WebSocketPair`. It acks frames immediately, forwards JPEGs as binary and hello/error as JSON, ignores client messages, and mirrors close. Close codes 4401 (not connected), 4404 (no rental / no connection) and 4502 (unreachable).
- Egress: `_ugecy/status` answered locally; method+path allowlist (403 otherwise); 503 not_configured; 401 triggers one refresh and one retry; the body is buffered for replay.

## Verify
- `pnpm exec tsc -p worker/tsconfig.json --noEmit`: clean.
- `pnpm test:worker`: 43/43 pass.
- wrangler `deploy --dry-run` with containers and assets removed: OK.

## Deviations
- DO RPC surface is higher-level (connect/status/select/disconnect/token) instead of save/clear, so serialization lives in one place.

## Change requests
- None. The web plan (04-03) can rely on `/api/glasshand/*` and on stream close codes 4401/4404/4502.

## Risks
- The relay sends the bearer to whatever `controlUrl` the API returns (https/wss only; no host pinning). Pin the host once Glasshand's control domain is known.
- Not exercised against live Glasshand: wss to https conversion and outbound WebSocket behaviour are untested here. The relay is only unit-tested via `pipe`.
- A transient refresh failure surfaces as 502 to the container and as the status `message` to the browser.

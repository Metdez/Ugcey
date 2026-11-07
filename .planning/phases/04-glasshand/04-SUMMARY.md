# Phase 04 summary: Glasshand live iPhone

**Built** (3 parallel Sonnet executors; see 04-01, 04-02, 04-03 SUMMARYs):
- **Edge (Worker):**
  - OAuth device flow (`/api/glasshand/{connect,status,select,disconnect}`).
  - Tokens kept only in AgentRuntime DO SQLite, refreshed with rotation, refreshes serialized.
  - A `glasshand.internal` egress allowlist. The agent can view and send input only; checkout, billing and cancel calls are blocked.
  - A WebSocket relay that acks frames and forwards JPEGs. The orchestrator added host pinning so the bearer goes only to `*.glasshand.com` over TLS.
- **Python:**
  - `AutoDeviceProvider`: uses live Glasshand when connected and the mock otherwise, with a 15 s cache.
  - `GlasshandProvider`: viewport crop and `Input` mapping, with `control_taken` and `control_busy` receipts.
  - Qwen3.8 vision grounding (`describe`).
  - Device-operator prompt rewritten for a real iPhone.
- **Web:** Device tab with Connect Glasshand (code, countdown, approval link, polling), a rental picker, a live canvas cropped to the viewport, snapshot fallback with backoff, "Take control in Glasshand", Disconnect, and a sidebar status row.

**Verified:**
- Worker: 44 tests. Python: 104. Web: 19.
- Live vision check: Qwen3.8 returned exact element coordinates on the mock screen, about 16 s per look.
- Deployed: `/api/glasshand/status` returns 401 when locked. `connect` returns a real Glasshand `user_code` with an `app.glasshand.com/approve` link. Polling stays pending. `disconnect` clears it. `/api/device` falls back to the mock.

**Not verifiable here (needs the operator's rental):**
- Token exchange after approval.
- Rentals listing.
- The live WebSocket stream.
- Real taps.

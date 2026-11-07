# Phase 06: remove mock mode (operator directive: "no mock data allowed")

**Rule:** the product never fabricates data or simulates a provider.
- When a capability isn't connected, its mode is **"off"**. The tool returns a clear, actionable error and the UI shows "Not connected" with how to connect it.
- Mock classes may remain **only** as test doubles (`UGECY_INTERNAL_MODE=test`). They must never be selectable in edge or local mode, and the web app must never import fixtures at runtime.

**Contract:** `Mode = "live" | "off"` (TS, packages/contracts/src/models.ts). Python `ugecy/contracts.py` keeps `Literal["live", "off", "mock"]`, where `mock` only ever appears in tests.

| Capability | Live when | Off behaviour |
|---|---|---|
| LLM | always (Workers AI) | — |
| Research `fetch_page` | always (Browser Run / HTTP) | — |
| Research `web_search` | Firecrawl configured | Error: "Live web search not connected (add FIRECRAWL_API_KEY). Research on the iPhone or fetch specific URLs." No sample library. |
| Pattern memory | Vectorize | `search_patterns` returns only real stored patterns, never samples |
| Media | `HF_KEY` Worker secret (`has_higgsfield`) | `generate_media` and `estimate` return "Higgsfield not connected: set the HF_KEY Worker secret". The catalog stays listable. |
| Device | Glasshand connected and rental ready | Error: "No iPhone connected: connect Glasshand in the Device tab". No mock iPhone. |
| Publishing (API) | none yet (needs platform app review) | `publish_post` returns "Direct API publishing isn't connected; publish from the iPhone via the device-operator (with approval)". No demo accounts, no simulated publisher. |
| Analytics | none yet | `get_post_metrics` returns "No analytics source connected; read metrics on the iPhone with device_observe". |

**Data cleanup (orchestrator):** delete the `mode='mock'` rows from D1 `accounts`, `assets` and `posts`. The audit log stays immutable.

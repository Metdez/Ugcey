# State

## Project Reference
See: .planning/PROJECT.md (updated 2026-11-07)
**Core value:** An operator gives a product and a goal. The agent returns evidence-backed, original UGC scripts and assets, and every step it takes is visible and controllable.
**Current focus:** v1 shipped. Next is v2 (live providers, publishing adapters, device relay)

## Position
- Phase 1: done (scaffold + contracts)
- Phase 2: done (10 parallel Sonnet executors, all SUMMARYs in phases/02-build)
- Phase 3: done, deployed at https://ugecy.zh-a16.workers.dev (see phases/03-ship/03-01-SUMMARY.md)

## Decisions
See .planning/research/SUMMARY.md, "Locked decisions" L1–L12.

## Blockers / user actions
- R2 is not enabled. Enable it in the dashboard when you want media originals stored in R2.
- Cloudflare Access (Zero Trust) is not enabled. In the meantime an access-key cookie gate protects the app.
- No Firecrawl, Glasshand, or social-app credentials are available. Those providers run in mock or sample mode.

## Session log
- 2026-11-07: Ran the GSD research step (8 parallel researchers), wrote PROJECT, SUMMARY, REQUIREMENTS and ROADMAP, built the scaffold, froze the contracts, and dispatched Phase 2.
- 2026-11-07: Created Cloudflare resources: D1 `ugecy-db` (b70c37bc-cb91-4ae3-a3f7-5a6f9f004cd9), KV `ugecy-cache` (c3f019863287426fb60de2b822c95bf3), queues `ugecy-jobs` and `ugecy-jobs-dlq`, and Vectorize `ugecy-memory` (1024-d, cosine). The agent image builds locally with the CA passed as a BuildKit secret, then is pushed to registry.cloudflare.com with `--provenance=false --sbom=false`.
- 2026-11-07: Phase 2 executed in parallel, integration fixes applied, deployed to Cloudflare, and live smoke test passed.
- 2026-11-07: Phase 4 (Glasshand) built in parallel and deployed. The connect flow is verified against the live Glasshand API. Final verification is waiting on the operator's rental and approval.
- 2026-11-07: Phase 06 removed mock mode (web + python), v5 deployed, 3 demo accounts deleted from D1. 20 sample-derived Vectorize patterns remain (auto mode blocked the bulk delete; operator to run it).
- 2026-11-07: HF_KEY Worker secret set (with operator permission), so Higgsfield is live. A live estimate through the agent returned $0.004 for Soul. The Kling i2v estimate returns null without an image_url; the catalog hint is $0.54.
- 2026-11-07: Fixed the Device tab's live iPhone view, which flashed a snapshot and then went white at "LIVE · 0 fps". The client went live on `hello` before drawing any frame, the relay acked frames before render (against Glasshand's protocol), and `close(1011)` threw, so the browser never learned upstream died. Now snapshots stay up until a frame draws, the client acks after drawing, a 10 s no-draw watchdog falls back and reconnects, and `hello` geometry is validated. Verified in Chromium through the real `pipe()` against a protocol emulator (healthy, stall, error, bad geometry, pause). Still needs a check on the live rental after deploy.

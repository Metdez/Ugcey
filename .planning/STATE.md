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
- 2026-11-07: Phase 07 added continuous per-agent memory (episodes + lessons, reloaded every run) and stuck detection that sends agents to Firecrawl web_search. Image v17.
- 2026-11-07: Phase 08 shipped the Dropbox media library (OAuth connect, dropbox.internal, save_url backups and backfill, 5 tools, phone how-to). Images v19 and v20; D1 migration 0002 applied. Waiting on the operator to Connect.
- 2026-11-07: Big threads would not open (500 after ~5 s: "Server disconnected without sending a response." or a bare "Internal Server Error"; the UI showed only "Error"). Hydrating a thread read its whole checkpoint history in one `state.internal` call. Every step stores a full copy of `messages`, so that history grows with the square of the thread's length (~150 MB at 150 steps). One read then hit the Durable Object's RPC or memory limit; #6 lifted the run caps that had kept threads small. Hydration now loads only each namespace's latest checkpoint, its blobs and its writes. A thread left "running" by a container restart is settled to idle, and the status pill shows the error message. Follow-ups: prune superseded checkpoints and blobs on write (storage still grows), page `kvGet`, and return JSON errors from `state.internal`. `POST /api/runtime/restart` is public since #7.

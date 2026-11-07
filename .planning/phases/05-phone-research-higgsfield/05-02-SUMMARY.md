# 05-02 Higgsfield production engine: summary

## Files
- integrations/media/{higgsfield.py,catalog.yaml}, tools/media.py, agents/prompts/production-coordinator.md, skills/higgsfield-prompting/SKILL.md
- main.py `_startup`: calls `resume_media_jobs()` after deps/accounts (wrapped, logged, never blocks boot)
- tests/test_higgsfield_adapter.py, tests/test_higgsfield_tools.py (19 tests)

## Estimate bug (root cause)
`POST /estimate` has two shapes. Fixed-price models: `{"type":"estimate","credits","usd":"0.004","discount"}`. Metered models (Seedance, Wan, Ads Studio, motion-control): `{"type":"description","pricing_description":"..."}` with NO `usd`. The old code did `["usd"]`, hit KeyError and swallowed it, so None. Args were fine. `parse_estimate` now reads usd, else derives per-second rate x duration for the requested resolution from the text; token-only (Ads Studio) stays None. Kling/Marketing/MiniMax also return a `discount` block; usd is used as the charge (conservative if gross).

## Live estimates (free, defaults, 5 s where video)
soul/v2/standard $0.006 | marketing-studio/image $0.034 | ads-studio None (token-metered) | seedance t2v / i2v / r2v $2.311 (720p) | kling 3.0 std i2v $0.536 | wan-3.0 i2v 480p draft $0.25

## Done
- Verified args vs docs llms-full.txt; catalog trimmed to 8 verified models with defaults, `requires`, `use`, `cost_hint`. Dropped motion-control (needs video_url) and minimax h3 (2K only).
- Errors: 401/403/404/422/423/429/503 map to agent-readable HiggsfieldError text (validation list rendered, 429 includes wait seconds); generate_media returns `{"error"}`.
- Chaining: `image_asset_id` -> image_url, `reference_asset_ids` -> image_urls; requires completed image asset with public url (live); missing required arg rejected before any spend. `estimate_for_approval` handles chained args and unresolved assets.
- Durable polling: `resume_media_jobs()` (dedupes via `_polling`), poller tolerates 3 transient get errors, audits expires_at plus 7-day warning.
- Prompt and skill rewritten (pipeline, cost discipline, hands-only, mock disclosure, manifest).

## Tests
whole suite: 132 passed, 1 skipped (05-01 finished meanwhile). ruff clean.

## Change requests
- `Asset` (contracts.py, frozen) has no `expires_at`; it lives only in the audit detail and MediaJob outputs. Add `Asset.expires_at` if the UI should show it.
- tests/test_graph_build.py expectations need 05-01's new tools and skill.
- Note: `ruff --fix` run at repo level may have removed unused `noqa` comments in 05-01 device files.

## Skipped / risks
- Reference-to-video video_urls surcharge and 9:16 vs 16:9 pixel difference not in estimate (shortcut comment).
- Chained image URLs are the Higgsfield URLs (7-day life); no re-upload via /files/generate-upload-url.
- Secret HF_KEY still operator-set; mock until then.

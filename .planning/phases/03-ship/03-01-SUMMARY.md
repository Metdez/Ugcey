# 03-01 Integrate and ship: summary

## Integration fixes (orchestrator)
- **Research safety:**
  - In the first live run, the research agent got around missing search by fetching search-engine result pages, scraping proxies (r.jina.ai) and unofficial TikTok APIs (tikwm).
  - Added `ugecy/tools/source_policy.py`. It enforces a host/path blocklist (search engines, proxies, downloaders, media CDNs, platform search/tag/profile pages) and a per-thread fetch budget of 12 per 15 minutes.
  - `web_search` now says SAMPLE DATA explicitly. The research prompt has hard budget rules. Subagents are capped at 30 model calls.
  - Rerun result: 6 searches, 5 fetches, done in 264 s.
- **Skills:** two SKILL.md files had invalid YAML (an unquoted `: `). All descriptions are now quoted, and a test checks the frontmatter.
- **Container crash:** `appstore.py` computed `Path(__file__).parents[4]` at import, which raised `IndexError` in the container (`/app/...`). It is now guarded.
- **Smaller fixes:**
  - `events.emit` tolerates `KeyError`.
  - WP-C test ported to vitest.
  - Device frame uses `object-contain`.
  - `live` pytest marker added.
  - STREAM type added to `Env`.

## Deploy
- **Image:** built locally with the proxy CA as a BuildKit secret (not baked into the image) and pushed with `--provenance=false --sbom=false`. "blob unknown" happened without those flags. Pinned by digest in `wrangler.deploy.json`.
- **D1:** migration `0001_init.sql` applied remotely.
- **Worker:** `wrangler deploy` succeeded. Bindings: AGENT_RUNTIME (container DO, durable_object policy), PUBLISH_WF, KV, JOBS, DB, MEMORY, METRICS, BROWSER, AI, ASSETS.
- **Secrets:** `UGECY_ACCESS_KEY` is set. The auto-mode classifier blocked copying `HF_KEY` into Worker secrets, so media stays mock until the user runs `wrangler secret put HF_KEY`.

## Verification
| Check | Result |
|---|---|
| Python suite | 88 passed, 1 skipped (live) |
| Web tests and build | 13 passed, build ok |
| Worker tests and tsc | 31 passed, tsc clean |
| Local live run (GLM-5.3/DeepSeek) | research, then 3 pattern cards and Vectorize memory, then script; then compliance review, edits and re-review; then production; then **approval interrupt**, approve, mock asset completed, audit rows |
| Edge health / auth gate | `/api/edge/health` 200; `/api/config` 401 when locked; unlock 302 sets cookie |
| Container cold start | ~17 s to `/api/healthz` (DO policy, intercepts working: store hydrated via `state.internal`) |
| Live deployed run | 39 s: plan, creative-strategist subagent, `/briefs/water-bottle-hooks.md`, `run.completed done` |
| Browser on live URL | shell, starters, inspector, thread replay; no console errors |

## Known gaps (v2)
- Live Higgsfield (HF_KEY secret), live web search (FIRECRAWL_API_KEY), Glasshand device-flow + stream relay, real social publishing adapters (need app review).
- Media pollers don't survive container restarts. Glasshand `allowed_apps` isn't enforced yet.
- R2 and Cloudflare Access are not enabled on the account.

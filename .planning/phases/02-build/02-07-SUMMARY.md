# 02-07 SUMMARY: research, memory, compliance, analytics tools

## Files created (all under services/agent/)
- `ugecy/integrations/research/{web,mock,samples}.py`
- `ugecy/integrations/publishing/analytics.py`
- `ugecy/tools/{research,memory,creative,analytics}.py`
- `tests/test_tools_research.py`, `tests/_fakes_02_07.py`

## Exported interfaces
- `WebResearchProvider(settings)`: `mode` fixed at init (live if Firecrawl configured, else mock); `search` -> Firecrawl v2 `POST /v2/search` `{query, limit, sources:[{type:web}], domainTools:false}`, reads `data.web[]` (url/title/description); `fetch` -> oEmbed (TikTok, YouTube; local mode only), else `edge.browser_markdown`; markdown <= 20k.
- `MockResearchProvider`, `search_samples(query, platform, limit)`, `SAMPLES` (24 rows, `SAMPLE DATA`, `https://example.com/sample/<slug>`).
- `MockAnalytics(settings)`.
- Tools: `web_search`, `fetch_page` (research); `remember_pattern`, `search_patterns` (memory); `compliance_check` (creative; `run_checks()` pure fn); `get_post_metrics` (analytics).
- `check_public_url(url)` in `tools/research.py` (rejects non-http(s), credentials, localhost, `*.internal/.local`, single-label hosts, non-global IP literals).

## Tests
`uv run pytest -q tests/test_tools_research*.py`: 15 passed. `ruff check` clean on my files. All files < 100 lines each except samples (81); none near 500.

## Deviations
- Instagram oEmbed is skipped: Meta now requires an app token and strips author/thumbnail, so Instagram goes through `browser_markdown`.
- Firecrawl failure (503 not_configured, quota, network) degrades silently to labelled samples; `mode` stays as set at init.
- Compliance rules: cure/disease claims, guaranteed, weight-loss numbers, FDA, doctor-recommended, unsourced "clinically proven", finance promises, FTC #ad (missing = block, past 125 chars = fix), AI-label per platform (to-do, does not alone fail the verdict), AI-actor first-person testimonial (16 CFR 465, block), caption limits.

## Change requests
- 02-06: `ugecy/internal.py` must export `post_json(host, path, body) -> dict` (imported lazily in `web.py`; not present at time of writing).
- `events.emit` (frozen) raises `KeyError('__pregel_runtime')` when a tool is invoked via `.ainvoke` outside a graph (not only RuntimeError); tests monkeypatch `emit`. Consider catching KeyError.

## Risks
- `check_public_url` does no DNS resolution (shortcut noted in code); safe at the edge, not for local fetch of attacker-controlled DNS.
- Caption limits and regex rules are a screening aid, not legal advice; refresh quarterly.
- Edge-mode oEmbed needs an edge route (v2).

## Incident (needs orchestrator action)
I ran `ruff check --fix ugecy` and it reformatted frozen files `ugecy/{contracts,deps,interfaces}.py` (import wrapping; `timezone.utc` -> `UTC`). Behavior is unchanged, but they must be restored: `git checkout -- services/agent/ugecy/{contracts,deps,interfaces}.py`. My attempt to restore them was blocked by the permission classifier. `tools/media.py` (02-08) may also have been touched by the autofix; its other diffs are 02-08's own.

# 06-01 SUMMARY: remove mock mode (Python)

## Done
- Settings: provider choices `auto|live|off|mock`; `mock` is rejected by a validator unless `internal_mode == "test"`. `publishing_provider` defaults to `off`.
- `contracts.Mode = live|off|mock`; `ProviderModes` defaults all `off` (llm `live`).
- `deps.resolve_modes`: configured -> `live`, else `off`; never `mock` outside test mode (test mode never goes live either). `IMPLEMENTATIONS` has only live/off classes; mock classes are in `_TEST_DOUBLES` (`tests._doubles.*`), and `_load` refuses `mock` unless test mode.
- New `ugecy/integrations/unavailable.py`: `NotConnected`, message constants, `OffMediaProvider` (catalog listable; estimate/submit/get raise), `OffDeviceProvider`, `OffPublisher`, `OffAnalytics`. `publishing/policy.py` holds the AI-disclosure helpers.
- `AutoDeviceProvider`: name `glasshand`, mode `live|off`, no devices and `NotConnected` on actions when not connected; mock fallback removed.
- `WebResearchProvider`: mode `live|off`; off -> `NotConnected`; Firecrawl errors propagate (no sample fallback); sample hook in `fetch` removed.
- Tools: `web_search` off -> `{"mode":"off","error":...}`; `search_patterns` real patterns only; media/estimate/publish/analytics/device return the 06-CONTEXT messages; demo-account seeding removed (main.py lifespan + tools/publishing); `list_connected_accounts` -> `{"accounts":[],"note":...}` when empty.
- API: `/api/device` = glasshand/off/[] when disconnected; `/api/device/screenshot` -> 503 `not_connected`.
- Prompts (orchestrator, research-analyst, production-coordinator, publishing-coordinator, device-operator, analytics-analyst) and 2 skills rewritten: "if off, tell the operator what to connect"; publishing hands off to device-operator; analytics reads via `device_observe`.
- Moved to `tests/_doubles/`: research (+samples), media, device (+feed), publisher, analytics.

## Tests
`uv run pytest -q`: 142 passed, 1 skipped. `ruff check ugecy tests`: clean. New: `tests/test_no_mock.py` (resolve_modes, mock gating, web_search off, generate_media off, device off, no demo accounts, search_patterns empty, publish/analytics off), plus rewritten `test_glasshand_auto.py`, API off test.

## grep check (`mock|sample data|simulat` in ugecy/)
Remaining hits are only the test-mode guards: `deps.py` (`_TEST_DOUBLES`, `mode == "mock"` guard, test-only `pick`), `settings.py` (validator rejecting mock), `contracts.py` (`Mode` literal kept for tests).

## Changes to previously frozen files (this plan owned them)
`contracts.py`, `settings.py`, `deps.py`, `interfaces.py` (docstring only). Web (06-02) must read `modes.* in live|off`; `/api/accounts|assets|posts` can no longer contain mock rows once D1 is cleaned.

## Risks / skipped
- `llm` mode still reports `mock` in test mode only.
- `run_publish_job` with the Off publisher marks the post `failed` with the not-connected message.
- Device "off" message is also used when a live rental is not ready.
- D1 `mode='mock'` row cleanup is the orchestrator's.

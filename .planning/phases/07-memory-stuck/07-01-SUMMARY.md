# 07-01 summary: stuck recovery + continuous memory

## Built
- `ugecy/middleware/stuck.py`:
  - `detect()` is a pure detector. It works on the window since the last `web_search`/`fetch_page` and flags 3 errors in a row, the same phone screen 3 times while acting, or the same call with the same result 3 times. `steps_used` is ignored, and polling tools are excluded.
  - `StuckMiddleware` appends a `<stuck_recovery>` block to the system message for that model call only. It never stops, caps or denies anything.
- `ugecy/memory/experience.py`:
  - Episode extraction and markdown.
  - `/memories/episodes/<agent>.md` keeps the newest 60 records.
  - The fast model merges each episode into the `/memories/agents/<agent>.md` lessons (at most 25 bullets, with a no-credentials rule).
  - Writes run as background tasks with per-file locks. If the merge fails, the episode is still kept.
- `ugecy/middleware/memory.py`:
  - `LiveMemoryMiddleware` is deepagents' `MemoryMiddleware` changed to reload on every invocation.
  - `ExperienceMiddleware` (`aafter_agent`) records each run.
- `graph.py`:
  - Every specialist and the orchestrator get all three middlewares and a "Memory and getting unstuck" prompt footer.
  - The orchestrator drops `memory=` in favor of `LiveMemoryMiddleware`.
- `tests/test_memory_stuck.py`: 12 tests, including an end-to-end graph run. In it, a subagent repeats a tap, gets the nudge on the 4th model call, its lessons load into its prompt, and its episode and lessons files are written.

## Verification
- pytest: 160 passed, 1 skipped. ruff clean.
- Deployed as image v17.

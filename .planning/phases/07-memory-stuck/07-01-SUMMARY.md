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
- Live check on v17: a web-only research run wrote all four files (`agents/` and `episodes/` for research-analyst and the orchestrator).
- Deviation: the lessons GLM-4.7-flash wrote for the orchestrator were made up (models, dates and languages that appear nowhere in the run). Lesson merging moved to GLM-5.3 (the critic role), the prompt now requires lessons to be grounded in the run record, and the bad file was reset. Redeployed as v18.
- Live check on v18 (a forced loop: device_tap with no session). Both the `errors` and `repeat` detectors fired. The agent stopped retrying, diagnosed the cause with device_status, and saved a grounded lesson with edit_file. The GLM-5.3 orchestrator lessons are grounded.
- Live on an operator run (phone stuck in the Photos viewer). The `no_change` detector fired and the agent called web_search twice. That run's flash-written lessons included made-up items, so the device-operator lessons were rewritten from its episode record.

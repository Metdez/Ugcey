# 02-04 Summary: Python API, stream adapter, run manager

## Files created
- `services/agent/ugecy/main.py` (`create_app(agent=None, deps=None)`, `app`, `ensure_default_accounts`)
- `ugecy/runs.py` (`RunManager`, `Run`, `RunConflict`, `tool_mode`)
- `ugecy/stream/adapter.py` (`StreamAdapter`, `build_requests`, `text_of`, `file_text`, `is_retryable`)
- `ugecy/api/{__init__,common,errors,threads,runs,memories,misc,jobs}.py`
- Tests: `tests/test_stream_adapter.py`, `tests/test_api_runs.py`, `tests/test_api_misc.py`, fakes in `tests/_fakes_02_04.py`

## Exported interfaces
- `StreamAdapter(thread_id, run_id, model).start()/feed(part)/finish(cancelled)/fail(exc)` returns `list[UiEvent]`. It assigns `seq`.
- `RunManager.start(tid, input|Command) -> Run` (raises `RunConflict`), `.subscribe(run, since)`, `.cancel(tid)`, `.latest/.active/.forget/.shutdown`.
- Routes: every endpoint in api.ts, plus `GET /healthz`, `GET /api/healthz` (adds `version`), and `POST /jobs/publish` (not under /api; the `Idempotency-Key` header is required).
- Errors use the `{"error": {"code", "message"}}` envelope, including 404/422/500.
- The 409 code for an active run is `run_active`. A resume with an unknown interrupt returns 404 `no_pending_approval`.

## Tests
`uv run pytest -q`: 85 passed, 1 skipped (whole suite, including other plans' tests present now). `ruff check` is clean on all my files. Largest file is 215 lines.
Covered: the adapter (text, reasoning, subagent ns, interrupt dedupe, values diffing, custom events, errors) and the API against a real `create_deep_agent` with a scripted model, using `ASGITransport`. The API tests cover:
- thread, run, SSE, state, files
- reconnect with `since` and `Last-Event-ID`
- interrupt, then approve/edit/reject resume, including a subagent interrupt
- 409 and cancel
- a client disconnect that does not cancel the run
- error events, `/api/config`, memories, accounts, jobs

I also smoke-tested the real lifespan in test mode (real graph + persistence): accounts, config and memories all came back.

## Deviations
- `/healthz` stays exactly `{ok, service}` because `test_health` asserts it.
- `ns` is `tools:<task_id>`, not the task call id. The real link is `parent_call_id`, taken from `lc_subagent_tool_call_id` (events.ts comment is slightly off).
- `RunContext` is built with only the fields the dataclass has, because the current `ugecy.graph.RunContext` has no `thread_id`.
- Lazy imports of 02-05/06/08 modules inside the lifespan and handlers, so `ugecy.main` imports without them.

## Change requests
- 02-05: add `thread_id` to `RunContext` (the plan says it exists; the code does not). I handle both.
- 02-06: no `adelete_thread` is used on thread delete; checkpoints are orphaned (marked `# shortcut`).
- 02-08: `run_publish_job` must be idempotent per post, since my replay cache is per-process only.

## Risks
- `tool.started` carries the pre-edit args when an operator edits a call.
- The ApprovalRecord `requests` are persisted at interrupt time. The resume endpoint only updates status.
- The container has no internal auth token check (not in this plan).

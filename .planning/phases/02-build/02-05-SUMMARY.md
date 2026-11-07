# 02-05 Summary: Deep Agents graph, routing, subagents, middleware, skills

## Files created (all under services/agent/)
- `ugecy/llm/{workers_ai,routing}.py`: `ChatWorkersAI`, `make_model(role, settings)`, `models_for(settings)`.
- `ugecy/middleware/{audit,compat,limits}.py`: `AuditMiddleware`, `CompatMiddleware`, `limit_middleware(settings, fallback)`.
- `ugecy/agents/{research,creative,critic,production,publishing,device,analytics}.py`, `_base.py` (prompt loader), `prompts/*.md` (7 subagents + orchestrator).
- `ugecy/graph.py`; `ugecy/skills/<6 playbooks>/SKILL.md`, `skills/_memory/AGENTS.md`.
- Tests: `tests/test_graph_{build,compat}.py`, `tests/test_llm_workers_ai.py`, `tests/_fakes_02_05.py`.

## Exported interfaces
- `graph.RunContext(workspace_id="default")`, `graph.build_agent(deps, models=None)` (recursion_limit 400), `async graph.seed_store(store, workspace_id)` (async: uses `aput`/`aget`).
- `make_model(role, settings)`: edge -> `http://llm.internal/v1` + "intercepted"; local/test -> Cloudflare URL + token.
- Verified in installed source: `ModelCallLimitMiddleware`, `ModelRetryMiddleware`, `ModelFallbackMiddleware`, `TodoListMiddleware` all exist in langchain 1.4.9.

## Tests
`uv run pytest -q tests/test_graph_*.py tests/test_llm_*.py`: 19 passed, 1 skipped (live). Live smoke (UGECY_LIVE=1, glm-5.3, local mode) passed. Ruff clean on my files. Largest file 130 lines.
Covered: scripted end-to-end run (write_todos, context, `task` delegation to research-analyst), exact tool sets per subagent, GP has no tools, interrupt_on contains generate_media/publish_post, disabled agent dropped, audit entry and failure swallowed, compat think/text-tool-call/nudge, make_model per mode, seed_store (skills refreshed, AGENTS.md only if missing), skill frontmatter.

## Deviations
- `seed_store` is async. Subagents get `skills=["/skills/"]` (not inherited otherwise). CompatMiddleware lives in `middleware/compat.py` (plan path), not `agents/model_compat.py`.
- Limit/retry/fallback/compat/audit are applied to the orchestrator and every subagent (each has its own call counter).
- Audit maps domain `analytics` to `modes.publishing`; unregistered tools use `modes.llm`.

## Change requests
- 02-01 / pyproject owner: register pytest marker `live` (`markers = ["live: real Workers AI call"]`) to silence the unknown-mark warning.
- Stream/main owner: call `await seed_store(deps.store, workspace_id)` at startup and pass `context=RunContext(workspace_id=...)` on every `astream`/`ainvoke` (StoreBackend namespaces read `rt.context.workspace_id`).
- Tool owners (02-07/08): names in the agent modules must match exactly; `compliance_check` should accept platform/paid/AI flags; `publish_post` needs `ai_disclosure`.

## Risks
- `tools_for` raises KeyError at build time if a tool module is missing; modules must load first.
- Narration nudge is regex-based; a false positive costs one extra model call.
- Memory is loaded once per thread, so AGENTS.md edits show in new threads.

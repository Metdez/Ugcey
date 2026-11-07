# Ugecy: Pitfalls (PITFALLS dimension)

Researched 2026-11-07. Each pitfall gives warning signs, prevention, and owning phase. **[verified]** = reproduced locally with deepagents 0.7.34 / langgraph 1.2.20; **[docs]** = Cloudflare docs, Sep–Nov 2026.

Names follow ARCHITECTURE.md: `AgentRuntime` (container DO, per workspace), `ChatSession` (per thread), `EgressGateway`, `*.internal`.

Suggested phases: **Ph1** foundation and contracts · **Ph2** edge core · **Ph3** agent runtime · **Ph4** workspace UI · **Ph5** approvals and policy · **Ph6** integrations · **Ph7** hardening and cost.

## A. Agent behaviour

### P-01 Open-model tool calling is flaky
- **Warning signs:** `invalid_tool_call` blocks or tool calls as plain text; hallucinated tool names or bad JSON args; calls to the built-in `execute` tool; 400s after a cancelled run (dangling tool calls).
- **Prevention:**
  - Always pass a **pre-built** `ChatOpenAI(..., use_responses_api=False)`. The string `"openai:<model>"` makes deepagents' OpenAI provider profile force the Responses API, which Workers AI serves only for gpt-oss and non-streaming **[verified/docs]**.
  - Exclude `execute` via `register_harness_profile("openai", HarnessProfile(excluded_tools=…))`.
  - Keep 8 or fewer tools per agent, with short pydantic schemas.
  - Use `ToolErrorMiddleware`, `ModelRetryMiddleware` and `ModelFallbackMiddleware` (`PatchToolCallsMiddleware` is already in the stack). Reuse deepagents' `NemotronTextToolCallParser` pattern for text tool calls, and gate model swaps on a per-model eval set.
- **Phase:** Ph3 (eval gate Ph7)

### P-02 Recursion and delegation loops
- **Warning signs:** the same `(tool, args)` repeats; the orchestrator re-delegates the same task; runs pass about 100 supersteps; tokens spike.
- **Prevention:**
  - `create_deep_agent` binds `recursion_limit=9_999` **[verified]**. Always pass about 150 in the run config.
  - Put `ModelCallLimitMiddleware(run_limit=…)` on the orchestrator **and** in every subagent spec, since limits are per invocation.
  - Add `ToolCallLimitMiddleware` for costly tools; `LoopGuard` rejects the third identical call hash; map `GraphRecursionError` to `run.completed{error, error_code:"step_limit"}`.
- **Phase:** Ph3

### P-03 Summarization never fires and context overflows
- **Warning signs:** context-overflow errors despite summarization; latency grows every turn; scraped pages inline in messages.
- **Prevention:**
  - Without `model.profile.max_input_tokens`, deepagents summarizes only at **170k tokens and keeps 6 messages**. With a profile it summarizes at 85% **[verified]**. Set `profile=` on every `ChatOpenAI`.
  - Research tools write raw pages to `/research/*.md` and return summaries and paths.
  - Cap virtual file size; send media to R2.
- **Phase:** Ph3

### P-04 Parallel subagents and hidden tools
- **Warning signs:** `InvalidUpdateError` with two `task` calls in one step; the auto-added `general-purpose` subagent calls orchestrator tools; todos panel empty.
- **Prevention:**
  - Every custom state key written by subagents needs a reducer. Prefer files over new state keys.
  - Disable the general-purpose subagent with `GeneralPurposeSubagentProfile(enabled=False)`.
  - deepagents 0.7.34 dropped `TodoListMiddleware` from the default stack **[verified]**. Add it explicitly and test that `write_todos` is bound.
- **Phase:** Ph3

## B. Edge, container and streaming

### P-05 SSE and WebSocket delivery stalls
- **Warning signs:** tokens arrive in bursts; `content-encoding: gzip/br` on `text/event-stream`; disconnects after about 100 s idle; an idle tab keeps a DO billing.
- **Prevention:**
  - SSE responses set `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`, and send `: ping` every 15 s.
  - No GZip middleware in FastAPI.
  - Coalesce deltas in 50 ms batches; never drop non-delta events.
  - Prefer hibernating WS (`useAgent`) for idle viewers, and close SSE 10 s after `run.completed`.
  - Smoke-test with `curl -N` on the deployed host.
- **Phase:** Ph2

### P-06 Browser or DO connection used as the run's lifetime
- **Warning signs:** closing a tab cancels the run; a reload loses tokens; tabs disagree; the scaffold proxies `POST /runs` SSE straight from the container.
- **Prevention:**
  - Runs are background tasks. Events are pushed to `events.internal`. ChatSession dedups `(run_id, local_seq)`, assigns thread `seq`, and replays `since`.
  - A pending outbound fetch keeps a DO resident for at most **15 min**, and deploys reset DOs **[docs]**. Never hold one stream for a whole run.
- **Phase:** Ph2

### P-07 Cold starts and inactivity kill runs
- **Warning signs:** the first message after idle takes 3–10 s; runs die after the DO idles; "Network connection lost"; runs stuck `running`.
- **Prevention:**
  - On the raw API the container stops shortly after its DO goes inactive, and `sleepAfter` does not exist **[docs]**. Call `setInactivityTimeout` after every `start()` and in the constructor.
  - Re-arm a 60 s alarm while `active_runs>0`.
  - Pre-warm when the WS connects.
  - Use a slim `python:3.13-slim` + `uv` image with lazy imports.
  - ChatSession watchdog: 120 s without a batch means mark the run drained and auto-resume.
- **Phase:** Ph2/Ph3

### P-08 SIGTERM, rollouts and host moves
- **Warning signs:** every deploy fails active runs; duplicate side effects after a restart.
- **Prevention:**
  - The platform sends SIGTERM and allows **15 min** before SIGKILL; `rollout_active_grace_period` defaults to 0 **[docs]**.
  - On SIGTERM, call `RunControl.request_drain()` on every run. LangGraph stops at the next superstep with the checkpoint saved (`GraphDrained`) **[verified API]**.
  - Run uvicorn with `--timeout-graceful-shutdown 840` and call `POST /internal/drain` before rollouts. Side-effect tools must be idempotent, because a re-run superstep repeats them (P-13).
- **Phase:** Ph3

### P-09 Wrong container topology or API
- **Warning signs:**
  - `getByName("default")` is one container for everything, so it is a bottleneck and a blast radius.
  - Cancel or resume reaches a host that does not know the run.
  - Building on `@cloudflare/containers` `Container`, then `monitor()` rejects with "starts without image".
- **Prevention:**
  - Use one `AgentRuntime` per workspace. ChatSession records the host of the active run and holds the one-run lock.
  - Containers are stateless between runs.
  - The `default` policy is deprecated and the choice is immutable; the `Container` class does not support `durable_object` **[docs]**. Port its readiness, inflight and start-coalescing logic instead.
- **Phase:** Ph2

### P-10 Long operations inside a run
- **Warning signs:** a tool polls Higgsfield for minutes or sleeps until a publish time; runs exceed DO or alarm windows.
- **Prevention:** tools return `job_id` immediately. Workflows (`step.sleepUntil`, `waitForEvent`, retries) wait, then emit `asset.updated` and post status through `events.internal`. The agent checks status in a later turn.
- **Phase:** Ph6

### P-11 Custom checkpointer slow or wrong
- **Warning signs:** state load takes seconds (many `state.internal` calls); resume replays the wrong step; it breaks after a LangGraph upgrade.
- **Prevention:**
  - `messages` is a `DeltaChannel(snapshot_frequency=50)`. The default `aget_delta_channel_history` walks parents with `get_tuple`, up to 50 round trips **[verified source]**. Override it with `/cp/delta-history`.
  - Store blobs per channel/version, make `put_writes` an upsert, and implement async methods only. Pass `langgraph-checkpoint-conformance==0.0.2` and a kill-mid-run test before Ph4 depends on it.
- **Phase:** Ph3

### P-12 Event log and state bloat
- **Warning signs:** ChatSession storage grows quadratically; replays send megabytes; segment rows near the 8 MB cap; huge `values` parts.
- **Prevention:**
  - deepagents summarization keeps raw `state.messages` **[verified]**, so `values` grows. The mapper diffs only `todos`/`files`.
  - Pack 10 events or 512 KB per row (cloudflare/agents pattern).
  - Prune deltas 24 h after the terminal event. Send `snapshot` when `since` falls below the floor.
- **Phase:** Ph2/Ph7

## C. Safety, security, compliance

### P-13 Publishing not idempotent
- **Warning signs:** duplicate posts after a retry, Queue redelivery (at-least-once) or drain re-run; "unknown" outcomes after timeouts.
- **Prevention:**
  - Grants are single-use (`UPDATE … WHERE used_at IS NULL`). `PublishWorkflow` id is `post_id`, with `idempotency_key=sha256(grant_id)` and a unique index.
  - Persist `external_post_id` before marking success. After an ambiguous timeout, reconcile by querying the platform; never blind retry. Dedupe Queue messages.
- **Phase:** Ph6

### P-14 Approval bypass
- **Warning signs:**
  - A side effect with no approval row.
  - A subagent spec with its own `interrupt_on`: it **replaces** the inherited one, and `CompiledSubAgent`/`AsyncSubAgent` inherit nothing.
  - Side-effect tools on the orchestrator or general-purpose subagent.
  - Raw vendor passthrough hosts (`higgsfield.internal`), or a generic HTTP tool.
  - "Publish now" text in scraped pages.
  - `respond` offered on risky tools (LangChain's default includes it **[verified]**).
- **Prevention:**
  - Edge grants (D7) checked in `EgressGateway`. The container never holds social, device or Higgsfield credentials.
  - Generate a per-subagent `interrupt_on` from `Plugin.side_effect` with `["approve","edit","reject"]`.
  - A unit test asserts every side-effect tool is gated in every agent that binds it. Re-validate edited args against the tool schema. Grants have a TTL, every decision is audited, and fetched content is wrapped as untrusted data in prompts.
- **Phase:** Ph5

### P-15 Secrets leak
- **Warning signs:** keys in `envVars`, Dockerfile or `.env` in the image; tokens in tool output, prompts or logs; tracing ships prompts to a third party.
- **Prevention:**
  - `enableInternet:false`; credentials are injected only in `EgressGateway` **[docs]**.
  - The internal token is random per container start. OAuth tokens are AES-GCM encrypted in D1 and decrypted only in the gateway.
  - Use log redaction filters in Python and TS; tracing stays off unless it redacts; local-mode env keys never ship in the image (`.dockerignore`).
- **Phase:** Ph2

### P-16 CORS, auth and tenancy holes
- **Warning signs:** CORS headers being added at all; trusting the `Cf-Access-Authenticated-User-Email` header; `workspace_id` taken from the client body; WS/SSE without auth; the shared `ugecy_key` cookie used for multiple users.
- **Prevention:**
  - Same origin, so no CORS. Use Cloudflare Access, with the Worker verifying `Cf-Access-Jwt-Assertion` signature and `aud` (`jose`); pass identity to DOs and Python only over internal hops.
  - ChatSession checks workspace membership on every command and connection. POSTs require a custom header (CSRF).
- **Phase:** Ph2

### P-17 Scope creep into prohibited automation
- **Warning signs:** tools for account creation, warming, fingerprint or proxy rotation, or "avoid detection"; device actions off the allow-list.
- **Prevention:** a plugin review checklist; a device action allow-list plus a consent flag enforced in `glasshand.internal`; official APIs, or Glasshand within ToS, only.
- **Phase:** Ph5/Ph6

## D. Delivery and operations

### P-18 Workers AI rate limits and timeouts
- **Warning signs:** bursts of 429 when subagents run in parallel; long TTFT from the capacity queue **[docs]**.
- **Prevention:**
  - Paid frontier models allow **20 RPM per model per account** (50 with prepaid AI Gateway credits) **[docs]**.
  - Use a per-model token bucket (`RateLimiter` DO) in `llm.internal`, jittered retry on 429/503, and fallbacks across *different* models (separate buckets).
  - Cap concurrent `task` calls. Use an httpx read timeout of about 120 s with streaming, and `rejectIfBusy` for latency-sensitive calls.
- **Phase:** Ph3/Ph7

### P-19 Runaway cost
- **Warning signs:** no per-run token totals; unreviewed video generations; containers that never sleep; idle SSE pinning DOs.
- **Prevention:**
  - `usage` events roll up into `usage_daily`. Workspace and run budgets get a hard stop at `POST /runs` and in `llm.internal`.
  - Use cheap models for subagents and summarization. Higgsfield generation is `risk:"spend"` and goes through approvals. Set the inactivity timeout from config and use WS hibernation.
- **Phase:** Ph7 (budgets in Ph3)

### P-20 Mock modes that crash or lie
- **Warning signs:** boot fails without vendor keys; production silently on mocks; UI shows no MOCK badge.
- **Prevention:**
  - The gateway returns 503 `not_configured`, and the registry picks `Plugin.mock`. `AppConfig.modes` drives the badges.
  - `UGECY_REQUIRE_LIVE=publishing,media` fails boot in production.
  - E2E uses a scripted streaming chat model that yields real `tool_call_chunks`. `GenericFakeChatModel` drops tool calls when streaming **[verified]**.
- **Phase:** Ph1/Ph3

### P-21 The 500-line rule erodes
- **Warning signs:** the mapper or ChatSession grows past 500 lines; generated or vendored files get counted (`ui/sidebar.tsx` is 726).
- **Prevention:** `check-file-length.mjs` in CI (excludes `_gen/`, `components/ui/`, lockfiles); follow the per-responsibility file list in ARCHITECTURE §7 from day one.
- **Phase:** Ph1

### P-22 Contract and dependency drift
- **Warning signs:** TS and pydantic diverge (the hand-mirrored `contracts.py` rule); a renovate bump breaks streaming; docs show camelCase while the wire uses snake_case; forking archived UIs (deep-agents-ui, agent-chat-ui).
- **Prevention:**
  - Generate pydantic from TS (ARCHITECTURE §9), with golden ndjson fixtures on both sides.
  - Exact pins; bump `langgraph`/`langchain`/`deepagents` together after the fixture suite passes.
  - Keep the `EventSink` seam for a v3/A′ migration.
- **Phase:** Ph1/Ph7

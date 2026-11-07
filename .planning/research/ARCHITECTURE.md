# Ugecy: Architecture research (ARCHITECTURE dimension)

Researched 2026-11-07. Every version was checked on PyPI/npm that day.
- **[verified]** marks behaviour run locally against deepagents 0.7.34 / langgraph 1.2.20 / langchain 1.4.9, with a scripted streaming tool-calling model (subagent, todos, HITL interrupt and resume).
- **[docs]** marks developers.cloudflare.com pages updated Sep–Nov 2026.

**Reconciliation note.** This research ran in parallel with the scaffold commit `1ed53fc` (`packages/contracts/src/*`, `worker/`, `services/agent/ugecy/`), with `CLOUDFLARE.md` and with `UI-SPEC.md`. Where those choices are sound, this file **adopts their names**: `AgentRuntime`, `ChatSession`, `EgressGateway`, `*.internal` hosts and `UiEvent`. It defines only **additive deltas** (§3.3, §11), so parallel builders keep one contract.

## 0. Decisions at a glance

| # | Area | Decision | Confidence |
|---|---|---|---|
| D1 | UI↔agent protocol | **Custom typed event union `UiEvent`** (`packages/contracts/src/events.ts`, extended in §3.3). The backend produces it from the **stable** `astream(version="v2", subgraphs=True, stream_mode=["messages","updates","custom","values"])`. | High |
| D2 | Rejected | LangGraph Agent Server: `langgraph-api` 0.17.1 / `langgraph-runtime-inmem` 0.37.1 are **Elastic-2.0**; the in-memory runtime is dev-only and pickles to `.langgraph_api/`; production needs PG+Redis. AG-UI (`ag-ui-langgraph` 0.0.47, a 4.6k-line mapper) and AI SDK 7 `useChat` (linear message model) also rejected. The self-served Agent Streaming Protocol + `@langchain/react` is the **v2 upgrade path** (§3.1). | High |
| D3 | Delivery | Runs are background asyncio tasks in the container. The container **pushes** batches to `events.internal`, and the `ChatSession` DO (one per thread) assigns the thread-scoped `seq`. ChatSession logs events in SQLite and fans them out over hibernating WebSockets (`useAgent`) and SSE (`GET /api/threads/:id/stream?since=`). | High |
| D4 | Container | `scheduling_policy:"durable_object"` with the raw `ctx.container` API. **`AgentRuntime` owns one container per workspace** (`getByName(workspace_id)`, never a global `"default"`). The `@cloudflare/containers` `Container` class does not support that policy **[docs]**. | Medium-high |
| D5 | Secrets/egress | `enableInternet:false`. The only egress is `EgressGateway` virtual hosts. **Side-effect paths require edge-minted approval grants**, so vendor passthrough must not be a blind proxy (§4.3, D7). | High |
| D6 | Persistence v1 | `EdgeCheckpointSaver` (custom `BaseCheckpointSaver`) writes to the **`AgentRuntime` DO SQLite**. That DO is co-located with its container; rows up to 8 MB, 10 GB per object. Add checkpoint-shaped `state.internal/cp/*` endpoints next to the KV ones. `EdgeStore` (`BaseStore`) uses KV-mirror/D1. Gate: `langgraph-checkpoint-conformance` 0.0.2. | Medium |
| D7 | Side effects | Approve/edit decisions mint single-use grants `{tool, args_sha256, ttl}` in D1. The gateway consumes a grant atomically before any publish, spend or device call. | High |
| D8 | Contracts | Plain TS in `packages/contracts/src` (scaffold) stays the source of truth. `ts-json-schema-generator` 2.9.0 → JSON Schema → `datamodel-code-generator` 0.90.0 → pydantic. Golden fixtures are checked on both sides. | High |
| D9 | Modularity | TOML module manifest plus explicit import paths. `Plugin(build, mock, requires, side_effect)`. Mock mode switches on automatically when a capability is missing. | High |

## 1. Data flow
```
Browser  apps/web (React19, Tailwind4, shadcn; useAgent WS + REST; reducer applyEvent(snapshot, UiEvent))
  │ same origin (SPA from Workers Static Assets, /api + /agents on one Worker) → no CORS
  ▼
Worker "ugecy" (worker/index.ts, Hono): auth → routeAgentRequest → /api routing table (§4.1)
  ├─ /agents/chat-session/:thread  (WS)  ──────────────► ChatSession DO (Agents SDK Agent, per thread)
  ├─ /api/threads/:id/{runs,resume,stream,cancel} ─────►   SQLite: event log (packed, seq), run FSM, pending
  │                                                         interrupts, last snapshot; hibernating WS fan-out
  │                       dispatch(run) RPC ──────────────┐      ▲ events.internal (batched push)
  │                                                       ▼      │
  ├─ /api/* (everything else) ──► AgentRuntime DO (per workspace; SQLite: checkpoints, store mirror)
  │                                 └─ ctx.container :8000  Python 3.13 FastAPI + deepagents (ugecy/)
  │                                      egress only via EgressGateway (WorkerEntrypoint, has env+bindings):
  │      llm.internal → env.AI (Workers AI via AI Gateway; per-model RPM bucket)
  │      state.internal → AgentRuntime SQLite (/kv/*, /cp/*)     events.internal → ChatSession RPC
  │      bindings.internal → D1, Vectorize, Browser Run, Stream, Workflows, Analytics Engine
  │      higgsfield.internal · glasshand.internal · firecrawl.internal → vendor (keys injected; grants on writes)
  └─ Workflows (PublishWorkflow, CampaignWorkflow) · Queues (ugecy-jobs + DLQ) · R2/Stream (assets) · KV (flags)
```

## 2. Why these choices (evidence)
- **Cloudflare lifetimes [docs]:**
  - A pending outbound fetch keeps a DO resident for at most **15 min**, and deploys reset DOs. A browser- or DO-held stream therefore cannot carry a run, which motivates D3.
  - Under the raw API the container stops shortly after its DO goes inactive. Call `setInactivityTimeout` (max 6 h) and re-arm it after a DO restart.
  - SIGTERM gives **15 min** before SIGKILL.
  - The `default` policy is deprecated and the policy choice is immutable.
- **Checkpoint locality:** outbound handlers run on the same machine as the container [docs]. Checkpoint I/O to the owning `AgentRuntime` DO is therefore local, whereas a per-thread DO could be cross-region. Per-workspace write serialization is enough for v1 scale.
- **Gaps in the v3 stream [verified]:** no root lifecycle events, no `input.requested` (interrupts only appear on `run.interrupts` after the stream ends), and `tool-finished.output` is a Python `repr(Command(...))`. The v2 parts give everything needed:
  - `ns==()` is the orchestrator; `("tools:<id>",)` is a subagent.
  - `metadata.lc_agent_name` and `lc_subagent_tool_call_id` (see DEEPAGENTS.md §8).
  - `values` carries `todos` and `files`.
  - `updates.__interrupt__` carries HITL requests.

## 3. Frontend↔agent protocol

### 3.1 Options

| Criterion | A: Agent Server + `useStream` | A′: self-served Agent Streaming Protocol + `@langchain/react` 1.2.13 | **B: custom `UiEvent` (chosen)** | B2: AI SDK 7 `useChat` | C: AG-UI 1.0 |
|---|---|---|---|---|---|
| License | ELv2 (SaaS grey area) | MIT | ours | Apache-2.0 | MIT |
| Prod in CF Container | no (inmem dev-only) | yes | yes | yes | yes |
| Subagent tokens | yes | yes (`lifecycle.cause.tool_call_id`) | yes (`agent`, `ns`, `parent_call_id`) | data parts | `SUBAGENT_*` |
| Todos/files | values | values | `todos.updated`/`files.updated` | data parts | STATE_SNAPSHOT/DELTA |
| HITL | yes | we synthesize `input.requested` | `approval.requested`/`resolved` | tool approval | outcome + `resume[]` |
| History/reconnect | yes | `since` (we build) | `since`/`lastSeq` + `snapshot` (ChatSession) | needs store | none |
| Stability | n/a | protocol 0.0.21, v3 "experimental" | v2 stable | v7 major churn | adapter 0.0.x |
| Fit with UI-SPEC reducer | low | medium | **native** | low | medium |

Choose **B**. It uses the stable stream API, is already scaffolded, matches UI-SPEC's `applyEvent` snapshot model, and carries domain events (sources, assets, approvals, audit, device) as first-class types. Keep a seam: `ugecy/stream/emitter.py` exposes `EventSink.emit(UiEvent)`, so a later A′ adapter only rewrites the mapper. Do not fork `deep-agents-ui` or `agent-chat-ui`; both are **archived**.

### 3.2 Pinned stack (exact)
- **Python** (`services/agent/pyproject.toml`): `deepagents==0.7.34 langgraph==1.2.20 langchain==1.4.9 langchain-core==1.7.6 langchain-openai==1.7.4 langgraph-checkpoint==4.3.1 fastapi==0.162.1 uvicorn==0.54.0 sse-starlette==3.7.0 httpx==0.28.1 pydantic==2.14.3`.
  - Dev: `langgraph-checkpoint-sqlite==3.1.3 langgraph-checkpoint-conformance==0.0.2 datamodel-code-generator==0.90.0 pytest`.
- **Web:** `react@19.3.1 agents@0.33.0` (`agents/react` `useAgent`) `zustand@5.1.0 @tanstack/react-query@5.107.1`. Use `@microsoft/fetch-event-source@2.0.1` for the SSE fallback and tests.
- AI Elements (vercel/ai-elements, Apache-2.0) are copied in as presentational components: `Conversation`, `Message`, `Reasoning`, `Tool`, `Confirmation`, `Sources`, `Plan`, `Task`. Replace `import type … from "ai"` with contract types and keep the license headers.
- **Worker:** `wrangler@4.158.0 hono@4.13.17 agents@0.33.0 jose@6.2.15`, plus `@cloudflare/workers-types` (current) and `@cloudflare/vitest-pool-workers@0.23.0`. Port the readiness, inflight and start-coalescing logic from `@cloudflare/containers` (MIT/Apache) into `AgentRuntime`. Do not depend on the package.

### 3.3 `UiEvent` v1: deltas to the scaffold (`packages/contracts/src/events.ts`)
Envelope semantics change, while field names stay the same:
- `seq` becomes **monotonic per thread**, assigned by ChatSession. It was per run.
- The container sends `local_seq` (per run) for idempotent batch retries. ChatSession strips it.
- SSE frames use `id: <seq>` and `event: <type>`, and `: ping` every 15 s. WS frames are `{"kind":"event","event":UiEvent}`.

```ts
// added/changed members (keep every existing member of UiEvent unchanged)
import type { ApprovalRecord, AuditEntry, Decision, ThreadState } from "./models";
export type RunStatus = "done" | "interrupted" | "error" | "cancelled" | "drained";      // + "drained"
export type Risk = "publish" | "spend" | "device" | "data" | "none";
export type UiEventDelta =
  | (EventBase & { type: "run.queued"; position: number })                        // follow-up while a run is active
  | (EventBase & { type: "run.started"; model: string | null; parent_run_id: string | null;
                   trigger: "message" | "resume" | "auto_resume" })              // + parent_run_id, trigger
  | (EventBase & { type: "run.completed"; status: RunStatus; error_code?: string })  // "step_limit" | "budget" | ...
  | (EventBase & { type: "approval.requested"; interrupt_id: string; requests: ApprovalRequest[];
                   risk: Risk; expires_at: string })                              // + risk, expires_at; ns = origin agent
  | (EventBase & { type: "approval.resolved"; interrupt_id: string; status: ApprovalRecord["status"];
                   decided_by: string; decisions: Decision[] })
  | (EventBase & { type: "usage"; model: string; input_tokens: number; output_tokens: number; cost_usd?: number })
  | (EventBase & { type: "audit.appended"; entry: AuditEntry })
  | (EventBase & { type: "device.receipt"; session_id: string; action: string;
                   status: "ok" | "denied" | "error"; screenshot_asset_id?: string })
  | (EventBase & { type: "snapshot"; state: ThreadState });                       // sent when `since` < retained floor
// models.ts: ApprovalRequest gains `risk: Risk` (estimated_cost_usd stays)
```

Producer mapping (`ugecy/stream/mapper.py`, v2 parts):

| v2 part | UiEvent |
|---|---|
| `messages` chunk text/reasoning blocks | `message.delta` / `reasoning.delta` (coalesce 50 ms) |
| `messages` final | `message.completed` |
| `updates` with AIMessage tool_calls | `tool.started` (`task` also gives `subagent.started{call_id, subagent=args.subagent_type}`) |
| `updates` ToolMessage | `tool.completed`, with `output_preview` sanitized and ≤2000 chars, never `repr(Command)` |
| `values` at `ns==()` diff | `todos.updated` / `files.updated` (index only; content via REST) |
| `updates.__interrupt__` | `approval.requested` |
| `custom` `{type:"source"\|"asset"\|"progress"\|"usage"}` | the matching event |

### 3.4 Wire examples
```
id: 42
event: subagent.started
data: {"seq":42,"ts":"2026-11-07T14:00:01Z","thread_id":"th_1","run_id":"run_7f3","agent":"orchestrator","ns":[],"parent_call_id":null,"type":"subagent.started","call_id":"call_c2","subagent":"research-analyst","description":"Find 5 hook patterns for…"}

id: 43
event: message.delta
data: {"seq":43,"ts":"2026-11-07T14:00:02Z","thread_id":"th_1","run_id":"run_7f3","agent":"research-analyst","ns":["tools:d0ddcd9f"],"parent_call_id":"call_c2","type":"message.delta","message_id":"lc_run--01a1","text":"Hook #1: "}

id: 57
event: approval.requested
data: {"seq":57,"ts":"2026-11-07T14:03:10Z","thread_id":"th_1","run_id":"run_7f3","agent":"publishing-coordinator","ns":["tools:9a1b"],"parent_call_id":"call_p1","type":"approval.requested","interrupt_id":"6bed7200e9878599","risk":"publish","expires_at":"2026-11-08T14:03:10Z","requests":[{"tool":"schedule_post","agent":"publishing-coordinator","args":{"account_id":"acc_tt_1","asset_id":"ast_9","caption":"…","publish_at":"2026-11-08T17:00:00Z"},"description":"Schedule TikTok post","allowed_decisions":["approve","edit","reject"],"risk":"publish"}]}

: ping
```
- Resume: `POST /api/threads/th_1/resume {"interrupt_id":"6bed7200e9878599","decisions":[{"type":"edit","args":{"caption":"edited"}}]}` with header `Idempotency-Key`.
- The Python handler maps it to LangChain HITL form, `Command(resume={interrupt_id: {"decisions":[{"type":"edit","edited_action":{"name":tool,"args":…}}]}})`. Always use the **id-map** form, because parallel subagents can each interrupt.
- `respond` is never offered for risky tools. LangChain's default allows approve/edit/reject/respond **[verified]**.

## 4. Endpoints

### 4.1 Public (Worker routing table)

| Path | Served by | Notes |
|---|---|---|
| `GET /api/edge/health` | Worker | liveness; `?deep=1` pings D1, KV, AgentRuntime, ChatSession |
| `GET /api/healthz` · `GET /api/config` | Python | `AppConfig` (`modes`, `models`, `agents` from the registry) |
| `GET/POST /api/threads` · `GET/DELETE /api/threads/:id` | Python (D1 via `bindings.internal`) | `GET` returns `ThreadState`, which ChatSession's cached snapshot can serve when the container is cold |
| `POST /api/threads/:id/runs` `{message}` | **ChatSession** | 202 `{run_id}`, or SSE when `Accept: text/event-stream` (tails from the run's first seq); 409 `approval_pending`; follow-ups are queued |
| `POST /api/threads/:id/resume` `ResumeRequest` | **ChatSession** | validates a pending interrupt, records an audit entry, mints grants, dispatches `trigger:"resume"` |
| `GET /api/threads/:id/stream?since=<seq>` | **ChatSession** | SSE replay then tail; honours `Last-Event-ID` |
| `POST /api/threads/:id/cancel` `{mode:"graceful"\|"abort"}` | **ChatSession** | graceful = `RunControl.request_drain`; abort = cancel the task |
| `GET /agents/chat-session/:thread` (WS) | **ChatSession** | `useAgent`: same log, plus small state `{run_status, pending_approvals, last_seq}` |
| `GET /api/threads/:id/files?path=` · `GET/PUT /api/memories` | Python | FileContent from state / Store |
| `GET /api/assets` · `GET /api/approvals?status=` · `GET /api/audit` · `GET /api/accounts` · `GET /api/posts` | Python | D1 reads (scaffold `ApiResponses`) |
| `GET /api/device` · `GET /api/device/screenshot` | Python (device module) | only with consent and the module on |
| `/oauth/*` · `/webhooks/*` | Worker | OAuth callbacks (tokens encrypted in D1); Higgsfield/Stream webhooks → Workflows `sendEvent` |

**Auth.** v1 uses the scaffold's `ugecy_key` cookie and is acceptable for one operator. For multiple users, put **Cloudflare Access** in front. The Worker verifies `Cf-Access-Jwt-Assertion` (`jose`; signature plus `aud`) and passes `{user_id, email}` to DOs and to Python as `x-ugecy-user` over the DO hop only, never from the client.

### 4.2 Internal container API (`:8000`, reachable only through `AgentRuntime.getTcpPort`; per-start random `x-ugecy-internal` token)

| Path | Body → result |
|---|---|
| `POST /internal/runs` | `{run_id, thread_id, workspace_id, user_id, message? \| resume?: {[interrupt_id]: resume_value}, trigger, limits:{recursion, model_calls, budget_usd}}` → 202 |
| `POST /internal/runs/:run/cancel` | `{mode}` → 202 |
| `GET /internal/health` | `{ok, version, active_runs, draining, modes}`; AgentRuntime's alarm uses it |
| `POST /internal/drain` | stop accepting runs and drain active ones (pre-rollout) |
| `POST /jobs/<name>` | Workflow-invoked jobs (scaffold), `Idempotency-Key` required |

### 4.3 Egress hosts (scaffold `INTERNAL-API.md`, plus these additions)
- `events.internal`: `POST /threads/:tid/runs/:run/events {from_local_seq, events: UiEvent[]}`. Idempotent; it goes to ChatSession RPC. Batches flush every 50 ms, 32 events or 64 KB, with one in flight per run.
- `state.internal` adds checkpoint routes next to `/kv/*`:
  - `/cp/get-tuple {thread_id, ns, checkpoint_id?}`
  - `/cp/list {thread_id, ns?, before?, limit?, filter?}`
  - `/cp/put {…, checkpoint_b64, metadata, new_versions, blobs:[{channel,version,type,blob_b64}]}`
  - `/cp/put-writes {…, task_id, task_path, writes:[…]}` (upsert)
  - `/cp/delta-history {thread_id, ns, checkpoint_id, channels}`, which walks the parent chain **server-side**
  - `/cp/delete-thread`
- Grant enforcement in `EgressGateway`:
  - Writes to `higgsfield.internal` (generation POSTs), `glasshand.internal` (actions), and `bindings.internal/publish/schedule` must carry `x-ugecy-grant`.
  - The gateway recomputes `sha256(tool + canonical(args))`, then runs `UPDATE grants SET used_at=… WHERE id=? AND used_at IS NULL AND args_sha256=? AND expires_at>now`.
  - It forwards only when exactly 1 row changes; otherwise it returns 403 `grant_required`.
  - Status and read endpoints are allow-listed. Everything else is denied (no blind passthrough).
- `llm.internal`: add a per-model token bucket in a small `RateLimiter` DO, plus budget checks per workspace and run (`usage_daily`).

## 5. Run lifecycle
1. `POST /runs` reaches ChatSession. ChatSession checks the run lock (queueing a follow-up and emitting `run.queued` if busy) and the budget, then writes `runs(queued)`. It calls `AgentRuntime(ws).dispatch()`, which does `startAndWaitForPort`, `setInactivityTimeout(30m)`, then `POST /internal/runs` → 202.
2. The container builds the graph from the registry and runs `astream(…, version="v2", subgraphs=True, control=RunControl(), config={thread_id, run_id, recursion_limit})`. `mapper` produces UiEvents and `pusher` sends them to `events.internal`. ChatSession dedups by `(run_id, local_seq)`, assigns `seq`, packs 10 events or 512 KB per row, and broadcasts.
3. On interrupt, ChatSession receives `approval.requested`, stores the pending interrupt, writes the D1 approval, releases the lock, and receives `run.completed{interrupted}`.
4. On `POST /resume`, ChatSession validates the request, writes the audit entry, **mints grants**, emits `approval.resolved`, and dispatches the resume (`parent_run_id`).
5. A side-effect tool sends `x-ugecy-grant`. The gateway consumes it and creates `PublishWorkflow(id=post_id, idempotency_key=sha256(grant_id))`, or a media job. The tool returns `{job_id}` at once. Long waits happen in Workflows (`step.sleepUntil`, `waitForEvent`), never in a run.
6. Liveness: `AgentRuntime` re-arms a 60 s alarm while `/internal/health.active_runs>0` and re-applies `setInactivityTimeout` in its constructor. ChatSession's watchdog marks a run `drained` and auto-resumes (`input=None`) when no batch has arrived for 120 s and the host does not know the run.
7. SIGTERM: in the uvicorn lifespan (`--timeout-graceful-shutdown 840`), call `request_drain()` on every run. LangGraph stops at the next superstep with the checkpoint saved (`GraphDrained`). The container emits `run.completed{drained}` and ChatSession re-dispatches.
8. Reconnect: WS reconnects with `last_seq`, or SSE with `since`. If `since` is below the retention floor, ChatSession sends `snapshot` and then tails.

## 6. Persistence

| Store | Holds | Notes |
|---|---|---|
| `AgentRuntime` DO SQLite (per workspace) | `checkpoints`, `checkpoint_blobs` (per channel/version, PostgresSaver layout), `checkpoint_writes`, the scaffold's `kv` (store mirror) | co-located with the container; 8 MB/row, 10 GB/object **[docs]**; 30-day PITR |
| `ChatSession` DO SQLite (per thread) | `events` (packed segments; only the latest `values`-derived event per kind is kept), `runs`, `pending_interrupts`, `snapshot` (last `ThreadState`) | thread-scoped seq; hibernating WS; deltas pruned 24 h after the terminal event |
| D1 `ugecy-db` | scaffold tables (`threads`, `audit`, `assets`, `posts`, `accounts`, `approvals`) plus **`grants`**, `usage_daily`, `runs_index` | 2 MB/row, 100 params/query; use `batch()` **[docs]** |
| KV · R2/Stream · Vectorize · Queues/Workflows | flags/routing/cache · media · memory/research embeddings · durable side effects | as in CLOUDFLARE.md |

`ugecy/persistence/edge_saver.py`:
- It is async only; sync methods raise, so the code must call `aget_state`.
- Blobs are `serde.dumps_typed` + base64, opaque to the edge.
- It **overrides `aget_delta_channel_history`** with `/cp/delta-history`. `DeepAgentState.messages` is a `DeltaChannel(snapshot_frequency=50)`, and the default implementation walks parents one `get_tuple` at a time, which means up to 50 round trips **[verified source]**.
- `put_writes` is an upsert.

Gate: pass `langgraph-checkpoint-conformance==0.0.2` against `services/agent/tests/fakes/state_internal.py` (in-memory SQLite with the same routes). Then kill the container mid-run in `wrangler dev` and resume.
- Local mode (`UGECY_INTERNAL_MODE=local`) uses `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite` 3.1.3).
- Tests use `InMemorySaver`.

**v2 options:**
1. Shard checkpoints per thread into ChatSession if per-workspace write contention appears.
2. Vectorize-backed `EdgeStore.search`.
3. Postgres (`langgraph-checkpoint-postgres` 3.2.0 on Neon) only as an emergency fallback. It needs `enableInternet:true` (port 5432; Hyperdrive is not reachable from containers), which weakens D5.

**Rejected:** SQLite-on-disk plus snapshots (needs the durable_object policy, tied to the image version, 30-day TTL, single host); D1 as checkpointer (2 MB rows, one writer for every thread).

## 7. Repo layout and ownership (aligned to the scaffold)
```
apps/web/src/{app,lib/api,stores,features/{chat,threads,inspector/<tab>,approvals,assets,device},components/{ui,ai}}
worker/index.ts (exports only) · worker/app.ts (Hono routes) · worker/routes/*.ts
worker/durable/{agent-runtime,agent-runtime-lifecycle,chat-session,chat-session-log,chat-session-runs,rate-limiter}.ts
worker/egress/{gateway,llm,state,events,bindings,vendors,grants}.ts · worker/workflows/*.ts · worker/lib/{auth,crypto,audit}.ts
migrations/*.sql · wrangler.jsonc
services/agent/ugecy/{main.py,registry.py,settings.py,contracts/_gen/*.py}
  api/{threads,runs,internal,memories,assets,approvals}.py · stream/{mapper,sanitize,pusher,emitter}.py
  agents/{factory,orchestrator,research_analyst,creative_strategist,production_coordinator,publishing_coordinator,device_operator,analytics}.py
  tools/<domain>.py · integrations/{media,publishing,device,research}/{live,mock}.py · llm/{workers_ai,scripted}.py
  persistence/{edge_saver,edge_store,local}.py · middleware/{loop_guard,usage,audit,budget}.py · config/ugecy.toml
packages/contracts/src/{models,events,api}.ts · schema/*.json (gen) · fixtures/{events/*.ndjson,rest/*.json} · INTERNAL-API.md
scripts/{gen-contracts.sh,check-file-length.mjs}
```

| Builder | Exclusive write scope | Depends on |
|---|---|---|
| 1 contracts | `packages/contracts/**`, `ugecy/contracts/_gen` | none (frozen after Phase 1; changes by PR plus fixtures) |
| 2 worker-core | `worker/{index,app}.ts`, `worker/routes`, `worker/lib`, `worker/workflows`, `migrations`, `wrangler.jsonc` | contracts |
| 3 worker-durable | `worker/durable/**`, `worker/egress/**` | contracts, `lib/*` (read) |
| 4 agent-runtime | `ugecy/{main.py,api,stream,persistence}`, Dockerfile | contracts |
| 5 agent-graph | `ugecy/{registry.py,settings.py,agents/factory.py,agents/orchestrator.py,middleware,llm}`, `config/ugecy.toml` | runtime ports |
| 6 agent-plugins | `ugecy/agents/<subagent>.py`, `ugecy/tools`, `ugecy/integrations` | registry API |
| 7 web-shell+chat | `apps/web/src/{app,lib,stores,features/chat,features/threads}` | contracts, fixtures (MSW) |
| 8 web-inspector | `apps/web/src/{features/inspector,approvals,assets,device,components/ai}` | contracts, `inspector/registry.ts` |

Rules:
- Shared lists (`worker/routes/index.ts`, `worker/egress/gateway.ts` host map, `config/ugecy.toml`, `inspector/registry.ts`) take one entry per line, sorted.
- Cross-scope needs go through contracts or `ports.py` / `*.port.ts`.
- CI fails on source files over 500 lines (skips `_gen/`, `components/ui/`, lockfiles). The scaffold's `ui/sidebar.tsx` (726 lines) is vendored and exempt.

## 8. Modularity

### 8.1 Registry (`services/agent/ugecy/registry.py`, ~40 lines)
```python
from __future__ import annotations
import importlib, os, tomllib
from dataclasses import dataclass
from typing import Any, Callable, Literal

Kind = Literal["llm", "persistence", "middleware", "media", "publishing", "device", "research", "tool", "subagent"]
ORDER: tuple[Kind, ...] = ("llm", "persistence", "middleware", "media", "publishing", "device", "research", "tool", "subagent")
Factory = Callable[["BuildCtx", dict[str, Any]], Any]

@dataclass(frozen=True)
class Plugin:
    kind: Kind
    name: str
    build: Factory
    mock: Factory | None = None              # chosen when caps are missing or mode == "mock"
    requires: tuple[str, ...] = ()           # capability names reported by the edge (never secret values)
    side_effect: str | None = None           # "publish" | "spend" | "device": HITL gate and grant required

@dataclass
class BuildCtx:
    caps: frozenset[str]
    mode: Literal["live", "mock"]
    built: dict[str, Any]                    # "kind:name" -> instance; later kinds read earlier ones
    modes: dict[str, str]                    # "kind:name" -> "live" | "mock", for AppConfig.modes

def enabled_modules(path: str) -> list[tuple[Plugin, dict[str, Any]]]:
    with open(path, "rb") as fh:
        modules = tomllib.load(fh)["modules"]
    picked = []
    for key, cfg in modules.items():          # key = "subagent.research_analyst"
        env = os.getenv("UGECY_MODULE_" + key.replace(".", "_").upper())
        if (env.lower() in ("1", "on", "true")) if env else cfg.get("enabled", False):
            picked.append((importlib.import_module(cfg["module"]).PLUGIN, cfg.get("config", {})))
    return sorted(picked, key=lambda pc: ORDER.index(pc[0].kind))

def build_all(ctx: BuildCtx, picked: list[tuple[Plugin, dict[str, Any]]]) -> dict[str, Any]:
    for plugin, conf in picked:
        missing = [c for c in plugin.requires if c not in ctx.caps]
        live = ctx.mode == "live" and not missing
        factory = plugin.build if live else plugin.mock
        if factory is None:
            raise RuntimeError(f"{plugin.kind}:{plugin.name} needs {missing} and has no mock")
        key = f"{plugin.kind}:{plugin.name}"
        ctx.built[key], ctx.modes[key] = factory(ctx, conf), ("live" if live else "mock")
    return ctx.built
```
`agents/factory.py` assembles `create_deep_agent(...)`:
- `model`: a pre-built `ChatOpenAI(base_url="http://llm.internal/v1", use_responses_api=False, profile={"max_input_tokens": N})`.
- `tools`: orchestrator tools, with **no side-effect tools**.
- `subagents`: `[SubAgent…]`. Each spec gets its **own** `interrupt_on`, derived from `Plugin.side_effect` with `allowed_decisions=["approve","edit","reject"]`.
- `middleware`: `[TodoListMiddleware(), ModelCallLimitMiddleware(run_limit=…), ToolErrorMiddleware(), ModelRetryMiddleware(), LoopGuard, Usage, Audit]`. `TodoListMiddleware` is **not** in the deepagents 0.7.34 default stack **[verified]**.
- `backend`: `CompositeBackend(StateBackend(), {"/memories/": StoreBackend(...)})`.
- Also pass `checkpointer`, `store`, and `memory=["/memories/AGENTS.md"]`.
- Call `register_harness_profile("openai", HarnessProfile(excluded_tools=frozenset({"execute"}), general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))`.

`config/ugecy.toml` (model ids per MODELS.md routing; env `UGECY_MODULE_SUBAGENT_DEVICE_OPERATOR=on` overrides):
```toml
[modules."llm.workers_ai"]
enabled = true
module = "ugecy.llm.workers_ai"
config = { routes = "MODELS.md table", max_input_tokens = 131072 }
[modules."subagent.research_analyst"]
enabled = true
module = "ugecy.agents.research_analyst"
[modules."subagent.device_operator"]
enabled = false
module = "ugecy.agents.device_operator"
```

### 8.2 Web and edge slots
- **Web:** `features/inspector/registry.ts` exports `TabDef[] = {id: InspectorTab, icon, module, badge(snapshot), load: () => import(...)}`. Tabs are filtered by `AppConfig.agents[].enabled` and `modes`. A pure `applyEvent` reducer is tested against `fixtures/events/*.ndjson`.
- **Edge:** route modules are mounted from `routes/index.ts`, gated by KV flags. Disabled egress hosts return 503 `not_configured`, and Python falls back to its mock (scaffold rule).

## 9. Contracts workflow (lowest friction given the scaffold)
1. Edit `packages/contracts/src/*.ts` (plain TS interfaces, as today).
2. `scripts/gen-contracts.sh` runs `ts-json-schema-generator@2.9.0 --path src/index.ts --type '*'` → `schema/contracts.json` → `datamodel-code-generator --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel --use-annotated --output ugecy/contracts/_gen/`. This replaces the hand-written "mirror 1:1 in contracts.py" rule.
3. CI re-runs generation, then `git diff --exit-code`.
4. Golden fixtures (`fixtures/events/*.ndjson` per scenario: chat, subagents, hitl-publish, drain-resume, reconnect-snapshot; plus `fixtures/rest/*.json`) are validated by pytest (pydantic) and vitest (Ajv over `schema/`). Web builders develop against MSW replays of them.

## 10. Reference repos (★ / licence checked 2026-11-07)

| Repo | ★ / licence | Copy | Avoid |
|---|---|---|---|
| langchain-ai/deepagents (`examples/content-builder-agent`, `async-subagent-server`) | 31.1k MIT | YAML subagent loader; stub-when-no-key mocks; FastAPI Agent-Protocol server shape | `FilesystemBackend` on container disk |
| langchain-ai/open-swe | 11.2k MIT | one middleware per policy (`notify_step_limit`, `sandbox_circuit_breaker`, `record_run_usage`, `workflow_push_guard`) | Managed-Deep-Agents dependency |
| xerrors/Yuxi | 7.6k MIT | FastAPI + deepagents: `202 + Idempotency-Key`, 409 while awaiting approval, cursor-validated SSE, worker-executed runs, steer vs follow-up queue | Redis/ARQ (we have DOs/Queues) |
| cloudflare/agents (`packages/agents/src/chat/resumable-stream.ts`) | 6.0k MIT | DO-SQLite chunk log: 10 chunks/segment, 512 KB/segment, paged replay, 1 h abandoned retention; `Agent` + hibernating WS for ChatSession | `AIChatAgent` (AI-SDK-shaped) |
| cloudflare/containers (lib) · containers-demos (213★) | MIT/Apache | inflight tracking, `IdentityTransformStream` proxying, start coalescing (issue #173) | `Container` class with the durable_object policy |
| langchain-ai/deep-agents-ui · agent-chat-ui | 1.7k / 3.3k MIT, **archived** | approval decision payloads; subagent cards keyed by `task` call id; `ensure-tool-responses` | forking either |
| langchain-ai/streaming-cookbook `react-custom-backend` | 58 Apache-2.0 | reference for the A′ upgrade (`LocalThreadSession` ⇄ `HttpAgentServerAdapter`) | v1 dependency |
| ag-ui-protocol/ag-ui · CopilotKit | 17.1k / 38.6k MIT | naming ideas (SUBAGENT_*, ACTIVITY_*) | second vocabulary |
| vercel/ai-elements | 2.5k Apache-2.0 | presentational components | `useChat` coupling |
| vstorm-co/full-stack-ai-agent-template | 2.0k MIT | FastAPI + Next streaming/auth template patterns | its WebSocket-only design |

## 11. Deltas the scaffold needs (actionable)
1. `INTERNAL-API.md`: replace `AGENT_RUNTIME.getByName("default")` with `getByName(workspace_id)`. Route `/api/threads/:id/{runs,resume,stream,cancel}` to **ChatSession**, not straight to the container, so runs survive tab close and replay across restarts.
2. Add `events.internal` and `state.internal/cp/*` (§4.3). With the `/kv/get` prefix scan alone, delta history needs N round trips.
3. Vendor hosts (`higgsfield.internal`, `glasshand.internal`) and `bindings.internal/publish/schedule` must enforce grants. They must not be raw passthroughs.
4. `events.ts`: make `seq` thread-scoped and add the §3.3 members. `models.ts`: add `ApprovalRequest.risk`, `grants` (D1), `usage_daily`. Map `Decision.edit.args` to LangChain `edited_action` in Python.
5. Container lifetime: `setInactivityTimeout` after every start and in the constructor, an alarm heartbeat while runs are active, and drain on SIGTERM. `sleepAfter` does not exist on the raw API **[docs]**.

## 12. Open questions
- `useAgent` state sync broadcasts state to every client. Keep its state tiny (`run_status`, `pending_approvals`, `last_seq`) and send events as messages. Measure fan-out cost with 3+ tabs.
- Measure `values` size per superstep: deepagents summarization keeps raw `messages` in state. Diff only `todos`/`files` in the mapper.
- Workers AI paid models allow **20 RPM per model per account** (50 with prepaid AI Gateway credits) **[docs]**. Size the limiter and the fallback chain with MODELS.md.
- Resolved: intercepts are capped at 128 entries (64 hostnames) and cannot be removed while running **[docs]**. Register the host set once and gate disabled modules inside the gateway.

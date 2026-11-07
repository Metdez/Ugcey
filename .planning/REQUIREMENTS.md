# Requirements: Ugecy v1

## v1 requirements

### Shell & chat (web)
- **SHELL-01**: The workspace has a 3-pane resizable layout: a left nav (threads, accounts), the chat, and a right inspector with an icon rail. Both side panes collapse with ⌘B and ⌘I and turn into sheets below 1024px.
- **SHELL-02**: ⌘K opens a command palette that runs starter prompts, navigation and inspector tabs.
- **SHELL-03**: Banners appear for mock mode, offline, and locked (401) states. A header shows the model chip and run status.
- **CHAT-01**: Assistant text streams in, with a collapsible reasoning section, tool lines, subagent lines that nest their activity, and an inline plan card.
- **CHAT-02**: Approval cards appear inline with Approve, Edit and Reject. The decisions are sent to `/resume`, and the run continues streaming afterwards.
- **CHAT-03**: Asset previews (image and video) appear in chat, plus a lightbox. The empty state offers starter prompts.

### Inspector (web)
- **INSP-01..09**: The inspector has nine tabs: Plan (todos), Agents (subagent runs and roster), Files (tree and viewer), Memory (`/memories` editable, `/skills` read-only), Sources, Assets, Approvals, Audit, and Device (mock iPhone frame, status, screenshot refresh).

### Agent (python)
- **AGENT-01**: A Deep Agents orchestrator delegates through `task` to 7 registered subagents: research-analyst, creative-strategist, compliance-critic, production-coordinator, publishing-coordinator, device-operator and analytics-analyst. Each can be toggled through `modules.py` or env.
- **AGENT-02**: Model routing uses Chinese Workers AI models per role, with a fallback model on 429 or error, a model-call limit, and retry.
- **AGENT-03**: Side-effect tools (`generate_media`, `publish_post`, `device_start_session`, `device_commit`) require HITL approval.
- **AGENT-04**: Long-term `/memories/` lives in the Store, with `AGENTS.md` loaded as memory. Seeded `/skills/` playbooks are read-only. Todos and files are thread state.
- **AGENT-05**: Every tool call writes an audit row with the agent, tool, status and mode.

### API & persistence (python)
- **API-01**: The REST endpoints match `packages/contracts/src/api.ts`.
- **API-02**: The SSE event stream matches `events.ts`. Runs continue when the client disconnects, and `/stream?since=` replays missed events.
- **API-03**: `/resume` maps UI decisions to LangChain HITL decisions, records the approval and writes an audit row.
- **PERS-01/02**: The checkpointer and store survive a container restart, through write-through mirrors to `state.internal`.
- **PERS-03**: The app store runs on D1 at the edge and on SQLite locally, from the same `migrations/0001_init.sql`.

### Capabilities (python)
- **RES-01**: `web_search` uses Firecrawl or sample data. `fetch_page` uses oEmbed plus Browser Run, and emits a `source.added` event.
- **RES-02**: `remember_pattern` and `search_patterns` use Vectorize semantic memory.
- **RES-03**: `compliance_check` is deterministic. It checks FTC `#ad` disclosure, banned health claims and the AI-disclosure flag.
- **MEDIA-01/02**: Higgsfield adapter (`estimate`, `submit`, `poll`) and a mock adapter. Assets are tracked in D1, and videos are ingested to Stream.
- **PUB-01/02**: `publish_post` sends a mock post with `ai_disclosure` required. Scheduled posts go through a Workflow.
- **DEV-01/02**: The mock iPhone provider renders screens, and the device tools are guarded by an approved session. A Glasshand REST provider is scaffolded.

### Edge (TypeScript)
- **EDGE-01**: The Worker serves the SPA and proxies `/api/*` to the `AgentRuntime` DO. The DO holds a container with the `durable_object` policy, internet off, and intercepts installed.
- **EDGE-02**: The egress gateway serves `llm.internal` (AI binding), `state.internal` (DO SQLite), `bindings.internal` and the vendor proxies, and denies everything else.
- **EDGE-03**: PublishWorkflow (`sleepUntil`, then `/jobs/publish`), a Queue consumer for media ingest, and a DLQ.
- **EDGE-04**: Bootstrap script for D1, KV, Queues and Vectorize. Migrations are applied.
- **EDGE-05**: The access-key cookie gate.
- **OPS-01**: Deployed at `https://ugecy.zh-a16.workers.dev`. A smoke test passes for health, a thread run streaming tokens, and the inspector populating.

## v2 (deferred)
- Live social publishing adapters after app review: TikTok, IG, YouTube, FB.
- Glasshand live stream relay through a `DeviceSession` DO, and the handoff page.
- Durable ThreadDO event log and approval grants enforced at the edge.
- R2 media originals; Cloudflare Access; custom domain for webhooks.
- AI Gateway aliases plus prepaid credits; scheduled research digests (cron); analytics feedback loop into memory.
- Campaign board; Soul ID character casting with a consent attestation.

## Out of scope
See `PROJECT.md`: account creation, warming, evasion, unapproved actions, gated scraping, and Anthropic models.

## Traceability
| Requirement | Phase / plan |
|---|---|
| SHELL-*, CHAT-*, INSP-* | 02-01, 02-02, 02-03 |
| API-*, AGENT-05 (approvals audit) | 02-04 |
| AGENT-01..05 | 02-05 |
| PERS-* | 02-06 |
| RES-* | 02-07 |
| MEDIA-*, PUB-*, DEV-* | 02-08 |
| EDGE-01, 02, 05 | 02-09 |
| EDGE-03, 04 | 02-10 |
| OPS-01 | 03-01 |

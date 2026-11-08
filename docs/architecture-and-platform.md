# Architecture & platform

Use LangChain Deep Agents as the orchestration layer: specialist agents, persistent task context, explicit tools, checkpoints, and auditable handoffs. Build capabilities as independently deployable modules rather than a monolith.

## Platform roles

| Platform | Intended role |
| --- | --- |
| Deep Agents | Task orchestration, context, delegation, and approvals |
| Glasshand | An approved iPhone-control integration, used only within device owner consent and platform policies |
| Higgsfield | Creative media generation and asset workflows |
| Cloudflare | Edge delivery, Workers, Queues, R2, D1/KV, AI services, security, observability, and access controls |

## Agent modules

- Research analyst: evidence-backed pattern discovery.
- Creative strategist: original briefs and scripts from findings.
- Compliance critic: rubric scoring, FTC `#ad`, AI-label and claim checks before generation or publishing.
- Production coordinator: Higgsfield asset jobs and review status.
- Publishing coordinator: approved platform connections, schedules, and logs.
- Device operator: Glasshand sessions and action receipts.
- Analytics analyst: post metrics, winners/losers, and playbook updates to memory (approval-gated).

Each module exposes a narrow contract, can be enabled or removed independently, and never bypasses approval, permission, or audit boundaries. To add or remove a module, add or remove its import in `services/agent/ugecy/modules.py`, or disable it at runtime with `UGECY_DISABLED_AGENTS` or `UGECY_DISABLED_TOOLS`.

## As built (v1)

```
Browser (React SPA) ── /api/* ──> Worker `ugecy` (Hono, public, no access key)
                                   └─> AgentRuntime Durable Object ──> Python container :8000 (FastAPI + deepagents)
Container egress (internet off) goes only through intercepted hosts, handled by EgressGateway in the Worker:
  llm.internal       -> env.AI (Workers AI: GLM-5.3, GPT-5.6 Terra, GPT-6 Luna, GLM-4.7-flash, Qwen3.8)
  state.internal     -> DO SQLite (LangGraph checkpointer and store mirrors, which survive restarts)
  bindings.internal  -> D1, Browser Run, Vectorize, Queues (Stream ingest), Workflows (scheduled publish), Analytics Engine
  higgsfield / firecrawl / glasshand .internal -> vendor APIs with keys injected at the edge
```

## Agent memory and stuck recovery

Every agent, including the orchestrator, runs Deep Agents memory with three middlewares (`services/agent/ugecy/middleware/{memory,stuck}.py`, `services/agent/ugecy/memory/experience.py`):

- `LiveMemoryMiddleware` loads `/memories/AGENTS.md` (shared brand and playbook) and `/memories/agents/<agent>.md` (that agent's lessons) into the system prompt. It reloads on every invocation, so lessons written earlier in a thread are picked up.
- `ExperienceMiddleware` runs after every subagent task and every orchestrator turn. It appends an episode (task, tools, errors, stuck events, result) to `/memories/episodes/<agent>.md` and has GLM-5.3 merge it into the lessons file. This runs in the background and never blocks a run. Agents can also add lessons themselves with `edit_file`.
- `StuckMiddleware` watches for three things: the same call with the same result three times, three errors in a row, or a phone screen that stays the same while the agent acts on it. When it sees one, it tells the agent, for that model call only, to use `web_search`/`fetch_page` (Firecrawl) and change approach. The orchestrator is told to delegate the lookup instead. It is never a cap or a stop.

All memory files live in the LangGraph Store (mirrored to DO SQLite) and show in the Memory tab.

## Dropbox media library

Every Higgsfield output is copied to the operator's Dropbox. Higgsfield deletes outputs after 7 days.

- **Connect:** Accounts → Dropbox → Connect. The operator approves on dropbox.com and pastes the code. The Worker keeps the refresh token in DO SQLite; the container reaches Dropbox only through `dropbox.internal`.
- **Copying:** `services/agent/ugecy/storage/backup.py` calls `save_url`, so Dropbox pulls the file itself. It runs after each media job, at startup and after Connect (the backfill). Files are named `/Ugecy/Videos/<date> <prompt words> <asset id 8>.mp4` (`Images/` for images).
- **Tools:** `dropbox_status`, `list_dropbox_media`, `browse_dropbox`, `save_to_dropbox` and `dropbox_backfill`, given to the production, publishing and device agents.
- **Phone:** the device agent gets videos onto the iPhone from the Dropbox app (Search, then ••• → Export → Save video).
- **After Higgsfield expiry:** `/api/assets` serves assets older than 6.5 days through private 4-hour Dropbox links.

The contracts that keep modules independent live in `packages/contracts/` (UI events, REST, internal edge API), `services/agent/ugecy/{contracts,interfaces,registry,deps}.py` and `worker/env.ts`. Decisions are recorded in `.planning/research/SUMMARY.md`.

## Models

Do not use Anthropic models. Choose non-Anthropic models per task; prefer Chinese models when they satisfy quality, cost, privacy, licensing, and deployment needs. Record the selection and rationale in the task context.

See [engineering-rules.md](engineering-rules.md) for implementation constraints and [research-and-integrations.md](research-and-integrations.md) before evaluating external tools.


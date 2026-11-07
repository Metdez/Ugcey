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
Browser (React SPA) ── /api/* ──> Worker `ugecy` (access-key cookie gate, Hono)
                                   └─> AgentRuntime Durable Object ──> Python container :8000 (FastAPI + deepagents)
Container egress (internet off) goes only through intercepted hosts, handled by EgressGateway in the Worker:
  llm.internal       -> env.AI (Workers AI: GLM-5.3, DeepSeek-V4.1-flash, Qwen3.8, GLM-4.7-flash)
  state.internal     -> DO SQLite (LangGraph checkpointer and store mirrors, which survive restarts)
  bindings.internal  -> D1, Browser Run, Vectorize, Queues (Stream ingest), Workflows (scheduled publish), Analytics Engine
  higgsfield / firecrawl / glasshand .internal -> vendor APIs with keys injected at the edge
```

The contracts that keep modules independent live in `packages/contracts/` (UI events, REST, internal edge API), `services/agent/ugecy/{contracts,interfaces,registry,deps}.py` and `worker/env.ts`. Decisions are recorded in `.planning/research/SUMMARY.md`.

## Models

Do not use Anthropic models. Choose non-Anthropic models per task; prefer Chinese models when they satisfy quality, cost, privacy, licensing, and deployment needs. Record the selection and rationale in the task context.

See [engineering-rules.md](engineering-rules.md) for implementation constraints and [research-and-integrations.md](research-and-integrations.md) before evaluating external tools.


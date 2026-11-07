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
- Production coordinator: Higgsfield asset jobs and review status.
- Publishing coordinator: approved platform connections, schedules, and logs.
- Device operator: cGlasshand sessions and action receipts.

Each module exposes a narrow contract, can be enabled or removed independently, and never bypasses approval, permission, or audit boundaries.

I want you to add more. This is just a general idea. This is completely flexible. 

## Models

Do not use Anthropic models. Choose non-Anthropic models per task; prefer Chinese models when they satisfy quality, cost, privacy, licensing, and deployment needs. Record the selection and rationale in the task context.

See [engineering-rules.md](engineering-rules.md) for implementation constraints and [research-and-integrations.md](research-and-integrations.md) before evaluating external tools.


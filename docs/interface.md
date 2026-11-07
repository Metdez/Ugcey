# Interface

The primary product surface is a focused chat workspace. It should make an agent's current task, evidence, tools, approvals, and durable context visible without overwhelming the operator.

## Layout

- Main pane: streaming agent conversation and task progress.
- Left sidebar: workspaces, campaigns, and active tasks.
- Right sidebar: context memory, sources, tool activity, assets, approvals, and audit trail.
- Optional device pane: a Glasshand iPhone stream only when the integration supports it and the device owner has consented; otherwise show session state and action receipts.

## Design process

Before any UI/UX decision, research current patterns with Firecrawl and Mobbin MCP. Use shadcn/ui as the implementation foundation, then adapt it to the product rather than copying an interface wholesale. Favor clear status, explicit approvals, accessible controls, and graceful loading/error states.

See [research-and-integrations.md](research-and-integrations.md) and [engineering-rules.md](engineering-rules.md).


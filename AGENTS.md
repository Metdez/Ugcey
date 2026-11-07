# Ugecy agent instructions

Read [CLAUDE.md](CLAUDE.md), then the relevant document in its context map. These instructions apply to every agent and task.

1. Before research or feature work, use Firecrawl to inspect current primary sources, relevant public implementations, and licensed GitHub references. Do not research for documentation-only tasks unless asked.
2. Before UI/UX work, research with Firecrawl and Mobbin MCP; implement with shadcn/ui patterns.
3. Before writing or changing code, invoke the Ponytail skill. Keep code modular, replaceable, and under 500 lines per source file.
4. Use Python for backend services and TypeScript for frontend services unless a documented exception is approved.
5. Prefer highly starred, actively maintained, license-compatible sources and reuse their code where it fits.
6. Do not use Anthropic models. Select capable non-Anthropic models—Chinese models are preferred where their capability, privacy, licensing, and deployment fit the task.
7. **No mock data, ever.** Never add mock modes, mock/sample/placeholder data, simulated providers or demo accounts to the product. If a capability is not connected, it reports `off` and tells the operator exactly what to connect. Test fakes live only under test directories and are injected by tests.

## Route by task

- Product, campaigns, publishing, approvals: [docs/product-and-operations.md](docs/product-and-operations.md)
- Deep Agents, Cloudflare, Glasshand, Higgsfield, models: [docs/architecture-and-platform.md](docs/architecture-and-platform.md)
- Research method and external integrations: [docs/research-and-integrations.md](docs/research-and-integrations.md)
- Chat workspace and iPhone-stream experience: [docs/interface.md](docs/interface.md)
- Code structure and delivery rules: [docs/engineering-rules.md](docs/engineering-rules.md)
- Plans, research, roadmap, and execution state (GSD workflow): [.planning/](.planning/PROJECT.md)

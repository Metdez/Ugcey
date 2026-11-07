# Engineering rules

## Mandatory workflow

- Invoke Ponytail before writing or modifying code.
- Use Firecrawl before feature work or research-driven decisions; use Mobbin MCP too for UI/UX work.
- Use modular, explicit interfaces so features can be added, swapped, disabled, or tested independently.
- Keep every source file at 500 lines or fewer; split by responsibility before crossing the limit.

## Ponytail checklist

Install the plugin with `/plugin marketplace add DietrichGebert/ponytail`, then `/plugin install ponytail@ponytail`. Until it is installed, follow these rules:

1. Read the code a change touches. List every caller, test, config and export the change must reach.
2. Take the first option that works:
   - don't build it at all;
   - reuse something in this repo;
   - use the stdlib or platform;
   - use an installed dependency;
   - write one clear line;
   - write the minimum new code.
3. Don't add abstractions, options or "for later" code nobody asked for. Never cut validation at trust boundaries, data-loss handling, security or accessibility.
4. Ship non-trivial logic with one small test. Mark a known limit with `shortcut: <limit>, <when to upgrade>`.

## Technology direction

- Backend: Python.
- Frontend: TypeScript.
- Edge: TypeScript is an approved exception for the Cloudflare Worker and its Durable Objects, because the Containers API is TS-only. Domain logic stays in Python.
- Orchestration: LangChain Deep Agents.
- Edge and platform services: maximize appropriate Cloudflare capabilities, with least-privilege access and observable failure handling.

## No mock data

The product never fabricates or simulates. It has no mock mode, no sample data, no demo accounts and no placeholder media. An unconnected capability reports `off` with a clear instruction to connect it. Test fakes live only in `tests/` (Python) or `*.test.ts` and `__fixtures__` (web), and tests inject them directly.

## Quality bar

- Prefer tested, maintained, license-compatible public implementations where they fit; document provenance and adapt deliberately.
- Preserve audit logs for external actions, approvals, and agent tool use.
- Treat modules, secrets, consent, rate limits, and failure recovery as first-class design concerns.

Return to [AGENTS.md](../AGENTS.md) for task routing and [architecture-and-platform.md](architecture-and-platform.md) for system boundaries.

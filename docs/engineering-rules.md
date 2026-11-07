# Engineering rules

## Mandatory workflow

- Invoke Ponytail before writing or modifying code.
- Use Firecrawl before feature work or research-driven decisions; use Mobbin MCP too for UI/UX work.
- Use modular, explicit interfaces so features can be added, swapped, disabled, or tested independently.
- Keep every source file at 500 lines or fewer; split by responsibility before crossing the limit.

## Technology direction

- Backend: Python.
- Frontend: TypeScript.
- Orchestration: LangChain Deep Agents.
- Edge and platform services: maximize appropriate Cloudflare capabilities, with least-privilege access and observable failure handling.

## Quality bar

- Prefer tested, maintained, license-compatible public implementations where they fit; document provenance and adapt deliberately.
- Preserve audit logs for external actions, approvals, and agent tool use.
- Treat modules, secrets, consent, rate limits, and failure recovery as first-class design concerns.

Return to [AGENTS.md](../AGENTS.md) for task routing and [architecture-and-platform.md](architecture-and-platform.md) for system boundaries.

# Ugecy

Ugecy is a modular, Deep Agents-powered workspace for compliant UGC campaign research, creation, review, and publishing. A React chat workspace talks to a Python Deep Agents service running in a Cloudflare Container, fronted by a Cloudflare Worker that also serves the static web app.

## Layout

```
apps/web/          Vite + React 19 + TS + Tailwind v4 + shadcn/ui
packages/          shared TS packages (contracts, ...)
services/agent/    Python (uv) FastAPI + Deep Agents service, Dockerfile
  ugecy/           api, stream, llm, agents, tools, integrations, persistence, skills
  tests/
worker/            Cloudflare Worker (Hono) - edge API, container proxy
wrangler.jsonc     Worker + static assets config
docs/              product, architecture, interface, engineering rules
.planning/         GSD plans, research, roadmap
```

## Local dev

Requires Node 22, pnpm 10, Python 3.13 and uv.

```sh
pnpm install

# web (proxies /api to http://127.0.0.1:8000)
pnpm dev:web

# agent service
cd services/agent
uv sync
uv run uvicorn ugecy.main:app --reload --port 8000
uv run pytest -q

# worker (after `pnpm build`)
pnpm exec wrangler dev

# checks / deploy
pnpm typecheck
pnpm deploy          # build web + wrangler deploy
```

## Context

Agent and contributor instructions: [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md). Plans and research: [.planning/](.planning/PROJECT.md).

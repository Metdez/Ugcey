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

## Live

- **URL:** https://ugecy.zh-a16.workers.dev. Unlock it once with `/api/edge/unlock?key=<UGECY_ACCESS_KEY>`, which sets a 30-day cookie.
- **Models:** Chinese models on Workers AI.
- **Mock mode:** media, publishing and device run as mocks until their credentials are added (see Deploy).

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

# checks
pnpm typecheck
pnpm test:worker
pnpm --filter web test
```

## Deploy (Cloudflare)

```sh
# 1. Build and push the agent image. Add --secret id=ca,... only when you are behind a TLS proxy.
docker build --provenance=false --sbom=false -t ugecy-agent:vN services/agent
pnpm exec wrangler containers push ugecy-agent:vN      # prints the sha256 digest
# 2. Render the config with real IDs and the digest-pinned image (wrangler.deploy.json is gitignored)
D1_ID=... KV_ID=... node scripts/render-config.mjs wrangler.jsonc wrangler.deploy.json
#    then set containers[0].images.agent = { "image": "registry.cloudflare.com/<acct>/ugecy-agent@sha256:<digest>" }
# 3. Migrate, build and deploy
pnpm exec wrangler d1 migrations apply ugecy-db --remote --config wrangler.deploy.json
pnpm build && pnpm exec wrangler deploy --config wrangler.deploy.json
# 4. Secrets. The optional ones switch providers from mock to live.
pnpm exec wrangler secret put UGECY_ACCESS_KEY --config wrangler.deploy.json
pnpm exec wrangler secret put HF_KEY --config wrangler.deploy.json            # Higgsfield "key-id:key-secret"
pnpm exec wrangler secret put FIRECRAWL_API_KEY --config wrangler.deploy.json # live web search
```

Resources are created by `scripts/bootstrap.sh`: D1 `ugecy-db`, KV `ugecy-cache`, queues `ugecy-jobs` and `ugecy-jobs-dlq`, and Vectorize `ugecy-memory` (1024-d, cosine).

## Context

Agent and contributor instructions: [CLAUDE.md](CLAUDE.md), [AGENTS.md](AGENTS.md). Plans and research: [.planning/](.planning/PROJECT.md).

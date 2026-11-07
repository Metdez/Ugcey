# 01-01 Scaffold - Summary

## Created
- Root: package.json (pnpm@10.28.0; scripts dev:web, build:web, build, deploy, typecheck), pnpm-workspace.yaml, .nvmrc (22), .gitignore extended, wrangler.jsonc, README.md.
- apps/web: Vite + React 19 + strict TS + Tailwind v4 + shadcn (new-york, neutral, CSS vars, lucide, `@/` alias). Placeholder App (shadcn Button "Ugecy"), `class="dark"` on html, title "Ugecy". vite.config.ts proxies /api to 127.0.0.1:8000, outDir dist.
- shadcn components in src/components/ui: button card badge tabs scroll-area separator tooltip dialog sheet resizable sidebar command dropdown-menu input textarea avatar skeleton sonner collapsible accordion alert popover select switch table hover-card progress toggle-group label kbd (all existed; toggle added as dependency of toggle-group).
- services/agent: pyproject.toml, uv.lock, .python-version (3.13), package dirs per spec (ugecy/{api,stream,llm,agents,tools,integrations/{media,device,research,publishing},persistence,skills/.gitkeep}), ugecy/main.py (/healthz), tests/test_health.py, Dockerfile, .dockerignore.
- worker/: index.ts (Hono; GET /api/edge/health, other /api/* 501), tsconfig.json.

## Resolved versions
react 19.3.1, vite 8.3.6, tailwindcss + @tailwindcss/vite 4.3.5, typescript 7.0.2 (web; root also ~5.9 for worker), shadcn CLI 4.23.0, lucide-react 1.70.0, zustand 5.x, react-markdown 10.1.0, hono 4.13.17, wrangler 4.158.0.
Python 3.13.18: deepagents 0.7.34, langchain 1.4.9, langgraph 1.2.20, langchain-openai 1.7.4, fastapi 0.162.1.

## Verified
- `pnpm --filter web build` and `pnpm typecheck` (web tsc -b + worker tsc): pass.
- `uv lock`, `uv sync`, `uv run pytest -q`: 1 passed.
- `wrangler deploy --dry-run` after web build: OK (ASSETS binding listed). No real deploy.

## Notes / skipped
- `docker build` fails in sandbox: uv in the build cannot trust the proxy CA (UnknownIssuer fetching from pythonhosted). No CA baked in; orchestrator should build on a normal network.
- The shadcn CLI `add` produced components importing `cn` from an npm package "cn" and no base theme; fixed manually: src/lib/utils.ts (clsx + tailwind-merge), imports rewritten to `@/lib/utils`, full neutral oklch theme written to src/index.css, tw-animate-css added. `shadcn init` was not run (components.json written by hand).
- ui/sidebar.tsx is 726 lines (vendored shadcn, exceeds 500-line rule; consider splitting or exempting).
- sonner.tsx uses next-themes `useTheme` without a provider (falls back to system theme); pass theme="dark" when wiring Toaster.
- Vite template's `lint: oxlint` script left in apps/web.

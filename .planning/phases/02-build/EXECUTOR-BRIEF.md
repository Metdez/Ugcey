# Executor brief (read this before your PLAN)

You are one of 10 parallel GSD executors. All of you run at the same time in the same checkout (/home/user/Ugcey, branch `claude/awesome-fermi-lro6p4`).

## Hard rules
1. **Write only the files your plan owns.** Read anything. If you need a change in a file someone else owns, don't make it: write the request into your SUMMARY under "Change requests" and code against the frozen contract.
2. **Never run `git commit`, `git push`, `git stash`, `git checkout` or `git reset`.** The orchestrator commits. Never run `wrangler deploy` (except `--dry-run`), and never create Cloudflare resources.
3. **Frozen contracts. Don't edit them; code against them exactly:**
   - `packages/contracts/src/{models,events,api}.ts` and `packages/contracts/INTERNAL-API.md`
   - `services/agent/ugecy/{contracts,interfaces,registry,settings,deps,modules,events}.py`
   - `worker/env.ts`
4. **Ponytail coding rules** (vendored from DietrichGebert/ponytail, MIT):
   - Take the smallest change that solves the whole task. Order of preference: reuse what exists, then the stdlib or platform, then an installed dependency, then minimal new code.
   - Don't add abstractions, options or "for later" code nobody asked for. Never cut validation at trust boundaries, data-loss handling, security or accessibility.
   - Non-trivial logic ships with one small test.
   - Mark a known limit with `# shortcut: <limit>, <when to upgrade>`.
   - End your reply with what you skipped and any risks.
5. **Every source file is ≤ 500 lines.** Split by responsibility; vendored shadcn `ui/*` files are the only exception.
6. Python 3.13, deps pinned in `services/agent/pyproject.toml`. If you need a new package, add it there with `uv add <pkg>` (you may edit pyproject.toml/uv.lock **only** with `uv add`) and say so in your SUMMARY. Web deps: `pnpm --filter web add <pkg>` (same rule).
7. **No Anthropic models anywhere.** No automated account creation, warming, or evasion features.
8. Research first where your plan says so: Firecrawl MCP (`mcp__firecrawl-mcp__firecrawl_search` / `firecrawl_scrape`; load them with ToolSearch `select:` if they aren't callable) for current docs. Frontend plans also use Mobbin MCP for any pattern the UI spec leaves open.

## Environment facts
- **Commands:**
  - Python: `cd services/agent && uv run pytest -q`
  - Web: `pnpm --filter web build`, `pnpm --filter web exec tsc -b`
  - Edge typecheck: `pnpm exec tsc -p worker/tsconfig.json --noEmit`
  - Wrangler dry run: `pnpm exec wrangler deploy --dry-run --outdir <scratch>`
- **Live Workers AI** (local mode only, if your plan needs a real model): `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` are in the env. Never print them. Prefer fake models in tests.
- **Research inputs to read for your area** (in `.planning/research/`):
  - `DEEPAGENTS.md` (API truth for deepagents 0.7.34)
  - `MODELS.md` (model quirks plus the `ChatWorkersAI` subclass)
  - `CLOUDFLARE.md` (edge)
  - `INTEGRATIONS.md` (Higgsfield / Glasshand)
  - `FEATURES.md` / `COMPETITORS.md` (product)
  - `UI-SPEC.md` (UI)
  - `SUMMARY.md` ("Locked decisions" override the research when they conflict)
- **Scratch space:** `/tmp/claude-0/-home-user-Ugcey/fa2c91df-9a17-597b-a1bb-bf83d8f15881/scratchpad/<plan-id>/`

## Done means
Your plan's `<verify>` commands pass, and you have written `.planning/phases/02-build/<plan-id>-SUMMARY.md` (≤ 80 lines) covering:
- files created
- exported interfaces
- tests run, with results
- deviations
- change requests to other plans
- risks

Then reply with a summary of ≤ 200 words.

## Shared test files
- `services/agent/tests/conftest.py` belongs to the orchestrator. Don't edit it. Put fixtures and fakes in `tests/_fakes_<plan-id>.py`.
- Registry isolation: `ugecy.registry.TOOLS` and `AGENTS` are module-global. A test that registers fakes must snapshot and restore them (e.g. `monkeypatch.setattr(registry, "TOOLS", {})`).

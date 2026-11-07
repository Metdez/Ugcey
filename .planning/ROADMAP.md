# Roadmap: Ugecy

## Overview
The work runs in three phases. Phase 1 laid the foundation and froze the contracts so the build could run in parallel. Phase 2 builds ten independent work packages at once. Phase 3 integrates them, deploys to Cloudflare, and verifies the result.

## Phases
- [x] **Phase 1: Foundation**: scaffold the monorepo and write the shared contracts.
- [ ] **Phase 2: Parallel build**: ten disjoint work packages (3 web, 5 Python, 2 edge).
- [ ] **Phase 3: Integrate & ship**: wire everything up, bootstrap Cloudflare, deploy, smoke-test, and hand over the URL.

## Phase Details

### Phase 1: Foundation
**Goal**: Every builder can work in its own folder against frozen interfaces.
**Requirements**: none directly; it enables all of them.
**Plans**:
- [x] 01-01: Scaffold the web, Python and worker skeletons (all builds green).
- [x] 01-02: Contracts: `packages/contracts/*`, `ugecy/{contracts,interfaces,registry,settings,deps,modules,events}.py`, `worker/env.ts`.

### Phase 2: Parallel build
**Goal**: Each package is implemented and its own tests and builds pass in isolation.
**Depends on**: Phase 1
**Success criteria**:
1. `pnpm --filter web build` passes. The UI renders a mock run, with every chat part and all inspector tabs populated.
2. `uv run pytest` passes in `services/agent`. A deep-agent run with a fake model streams contract events and pauses on an approval.
3. `wrangler deploy --dry-run` passes with all bindings.

**Plans** (all wave 1; there are no file overlaps):
- [ ] 02-01: Web shell, stores, API client and SSE (WP-A)
- [ ] 02-02: Web chat stream, approvals and assets (WP-B)
- [ ] 02-03: Web inspector, all 9 tabs (WP-C)
- [ ] 02-04: Python API, stream adapter and run manager
- [ ] 02-05: Python graph, models, agents, middleware and skills
- [ ] 02-06: Python persistence and D1 migrations
- [ ] 02-07: Python research, memory, compliance and analytics tools
- [ ] 02-08: Python media, publishing and device tools and providers
- [ ] 02-09: Edge core: Worker router, AgentRuntime DO, egress gateway, auth gate
- [ ] 02-10: Edge async: bindings API, PublishWorkflow, Queue consumer, bootstrap

### Phase 3: Integrate & ship
**Goal**: A live URL where the operator can chat with the agent and watch it plan, delegate, write files, ask for approval and generate media.
**Depends on**: Phase 2
**Success criteria**:
1. The deployed URL unlocks with the access key.
2. A real run on GLM-5.3 streams tokens, todos, subagent activity and files.
3. An approval card appears and resumes correctly.
4. Container restarts keep thread history.

**Plans**:
- [ ] 03-01: Integration, bootstrap, deploy, Playwright smoke test, docs update

# 02-09 Summary: edge core

## Files created
wrangler.jsonc (rewritten), worker/index.ts, worker/auth.ts, worker/proxy.ts, worker/do/agent-runtime.ts,
worker/egress/{gateway,llm,state,vendors}.ts, worker/test/edge.test.ts.
Stubs created only because missing (02-10 owns/overwrote): worker/egress/bindings.ts, worker/queues/consumer.ts, worker/workflows/publish.ts.
package.json: `test:worker` script; devDeps vitest ^5.1.0 and @cloudflare/workers-types upgraded to ^5.20261107.1 (old 4.x lacked `images`, `instance`, `inspect`).

## Exports
- `AgentRuntime` (fetch, kvGet/kvPut/kvDelete RPC with base64 values), `EgressGateway`, `PublishWorkflow` (re-export), default `{fetch, queue}`.
- auth: `sha256Hex, keyMatches, readCookie, cookieValid, unlock, requireKey`. llm: `filterSseLine, sseFilterStream, handleLlm, CHAT_MODELS, EMBED_MODELS`. vendors: `VENDORS, handleVendor`.

## Verified against current docs (differences from CLOUDFLARE.md / plan)
- Wrangler: container uses `images: {agent: {dockerfile, build_context}}` (not `image:`); DO reads `ctx.container.images.agent`. `exports` replaces `migrations`. Plan's `image: ./services/agent/Dockerfile` is invalid for the durable_object policy.
- `ctx.container` method names match CLOUDFLARE.md (start, running, getTcpPort, interceptOutboundHttp, setInactivityTimeout, monitor). `start()` needs `enableInternet`; `instance` optional.
- `ctx.exports` is untyped without `wrangler types` GlobalProps, so a cast sits in `egressGateway()` helper.
- Embeddings: Workers AI takes `{text: string[]}` and returns `{data: number[][]}`.

## Tests
- `pnpm exec tsc -p worker/tsconfig.json --noEmit`: pass.
- `pnpm test:worker`: pass (31 tests incl. 02-10's bindings tests; mine: SSE filter incl. split chunks, auth cookie/unlock, vendor allowlists).
- `wrangler deploy --dry-run` WITH container block: Docker image build is attempted and fails in the sandbox (`uv sync` has no network). Dry-run with container block removed (scratchpad/02-09/wrangler.nocontainer.jsonc): pass, all bindings listed.
- `pnpm --filter web build`: FAILS on other plans' in-progress files (apps/web/src/components/inspector/tabs/memory-tab.tsx `usePoll`, files/file-tree.tsx). Not mine; I created an empty apps/web/dist only for dry-run.

## Deviations
- Gateway calls `handleBindings(req, url, env, props)` (02-10's actual signature), not the plan's 3 args.
- `queue` wrapper casts batch to `MessageBatch<JobMessage>` for typing.

## Change requests
- 02-10: STREAM binding is not in frozen Env/wrangler; add it if media ingest needs it (wrangler.jsonc is mine; tell orchestrator).
- Orchestrator: add secrets (UGECY_ACCESS_KEY, HF_KEY etc.), real IDs, and consider digest-pinned image.

## Risks
- durable_object policy is public beta; mid-stream container death surfaces as a failed SSE.
- Workers AI SSE chunk shape for OpenAI-schema models unverified live; filter drops non-`choices` data lines.
- Vendor base URLs (firecrawl api.firecrawl.dev, glasshand api.glasshand.com) taken from INTERNAL-API.md; Glasshand token is a plain secret, not device-flow.
- Embeddings batch via `text` array; qwen3-embedding behaviour unverified live.

# CLOUDFLARE.md — Cloudflare architecture for Ugecy

Researched 2026-11-07. Primary sources are developers.cloudflare.com pages (fetched as `index.md`, most updated Sep–Nov 2026), blog.cloudflare.com, and the Cloudflare changelog. I also made read-only GET probes against api.cloudflare.com with the session token. Nothing was created, modified, or deployed. Snippets come from the official examples (`containers/examples/websocket`, `containers/examples/container-backend`, `containers/api/durable-object-container`, `configuration/outbound-traffic`). I adapted them for Ugecy. Lines marked **[unverified]** still need a Phase-0 spike.

## 0. Decisions (TL;DR)
1. **One Worker, `ugecy`.** It serves the React SPA (Workers Static Assets + `@cloudflare/vite-plugin`), `/api/*`, the Agents-SDK WebSocket routes, Workflows, the Queue consumer, and the Container DO. Do not use Pages: its docs say to "start new projects with Workers".
2. **Containers: GA since 2026-04-13.** Use the new **`scheduling_policy: "durable_object"`** with the native **`ctx.container` API**. Do not use the `@cloudflare/containers` `Container` class. Reasons: the `default` policy is **deprecated**, the Container class works only with `default` and is maintained only until **2026-12-31**, and the DO policy starts about 6× faster (median 648 ms). The DO policy is still **public beta**, which is the main risk.
3. **Container egress: deny by default.** Start with `enableInternet:false`. Register **outbound intercepts** for virtual hosts (`llm.internal`, `bindings.internal`, `state.internal`, `events.internal`, `<vendor>.internal`). These are handled by a `WorkerEntrypoint` in the Worker runtime, which holds every secret and binding. **The Python container never sees a token.**
4. **LLM path.** Python `ChatOpenAI(base_url="http://llm.internal/v1")` calls the egress handler, which calls `api.cloudflare.com/.../ai/v1/chat/completions` with `cf-aig-gateway-id: ugecy`. Workers AI serves GLM-5.3 / DeepSeek-V4.1-Flash / Qwen3.8 behind an **authenticated AI Gateway** that provides logs, costs, retries, model-alias fallback, and spend limits.
5. **Long-running state lives in Durable Objects (SQLite), not the container disk.** Disk is ephemeral, and hosts can SIGTERM a container at any time (15-minute grace).
6. **Approval and publishing pipeline: Workflows.** Use `step.do` with retries and rollback, `step.waitForEvent("approval")`, and `step.sleepUntil(publishAt)`. Side-effect fan-out goes through **Queues** with a DLQ.
7. **UI realtime: Agents SDK (`agents@0.33`).** A `ChatSession` Agent (a DO with hibernating WebSockets and state sync to `useAgent`) streams tokens and the todo, file, tool, and approval sidebars.
8. **Storage without R2.** Today: D1 (system of record and audit), KV (≤25 MiB blobs and cache), Stream (videos, copy-from-URL), Images (stills), DO SQLite (thread state), Vectorize (memory, bge-m3, 1024 dimensions). **Enable R2 in the dashboard soon.** It is the right home for originals and is the only blocker in the probe table that has a one-click fix.

---
## 1. Cloudflare Containers (state as of Nov 2026)
| Item | Fact (source) |
|---|---|
| Status | GA on 2026-04-13 ([changelog](https://developers.cloudflare.com/changelog/post/2026-04-13-containers-sandbox-ga/)). The `durable_object` scheduling policy and filesystem snapshots are **public beta** (2026-09-30, [blog](https://blog.cloudflare.com/faster-agent-sandboxes/)). The `default` policy is **deprecated** ([scheduling-policy](https://developers.cloudflare.com/containers/configuration/scheduling-policy/)). The policy is immutable once an app exists. |
| Instance types | lite 1/16 vCPU, 256 MiB, 2 GB · basic 1/4, 1 GiB, 4 GB · standard-1 1/2, 4 GiB, 8 GB · standard-2 1, 6 GiB, 12 GB · standard-3 2, 8 GiB, 16 GB · standard-4 4, 12 GiB, 20 GB. Custom sizes allow 1–4 vCPU, ≤12 GiB, ≤20 GB, and need ≥3 GiB per vCPU. **The DO policy does not accept `basic`. Its default is `lite`.** ([limits](https://developers.cloudflare.com/containers/platform/limits/)) |
| Account limits | 1,500 concurrent vCPU, 6 TiB memory, 30 TB disk. Image ≤ the instance's disk. Image storage 50 GB per account. Probe of `/containers/me`: 4 vCPU / 12 GiB / 20 GB per deployment. The DO policy has no `max_instances`. |
| Pricing | Billed per 10 ms while running. Workers Paid includes 25 GiB-h memory, 375 vCPU-min, and 200 GB-h disk per month, then $0.0000025/GiB-s, $0.000020/vCPU-s (active CPU only), and $0.00000007/GB-s. Egress costs $0.025/GB in NA/EU after 1 TB. **Example: standard-1 costs about $0.04/h awake** (memory dominates). Plus DO and Worker requests. Container logs move to Observability pricing on 2026-12-01 ([pricing](https://developers.cloudflare.com/containers/platform/pricing/)). |
| Cold start | DO policy p50 648 ms, p95 910 ms, p99 1.13 s, versus about 4 s before (blog). Python and LangChain imports add roughly 2–4 s. Pre-warm the container when the WebSocket connects. |
| Sleep | `ctx.container.setInactivityTimeout(ms)` accepts at most **6 h**. Set it again after a DO restart. `sleepAfter` exists only on the legacy class. Without a timeout, the container stops shortly after the DO goes idle. |
| Max duration | No fixed limit. HTTP requests and DO calls have **no wall-clock limit while the caller stays connected**. Host events send SIGTERM, wait up to 15 minutes, then SIGKILL. There is no runtime guarantee, so checkpoint every step ([FAQ](https://developers.cloudflare.com/containers/faq/)). |
| Disk | **Ephemeral.** Each start gets a fresh image filesystem. Snapshots (DO policy only) are ≤20 GB, have a 30-day TTL, and capture only the filesystem, not memory. FUSE→R2 is possible later. |
| Build/deploy | `wrangler deploy` makes the Worker live first, then builds the Dockerfile with the **local Docker** daemon and pushes it to `registry.cloudflare.com` (it pushes only layers that changed). The steps are **not transactional**. The first deploy takes "several minutes". Images must be **linux/amd64**. The DO policy accepts only a Dockerfile or a digest-pinned `registry.cloudflare.com/...@sha256:` image. `wrangler versions upload` does **not** ship images. DOs get no preview URLs. |
| Streaming | The DO's `getTcpPort(8000).fetch(req)` returns the container's Response unchanged, so **SSE streams through and WebSocket upgrades survive**: "Return the port response directly to preserve the WebSocket upgrade" ([websocket example](https://developers.cloudflare.com/containers/examples/websocket/)). |
| Gotchas | (a) On the DO policy, a deployed container's hostname is 64 chars, so Python `http.server`/`wsgiref` crash with `label too long`. Use uvicorn and do not resolve your own hostname. (b) Non-root users keep root capabilities. (c) Wrangler ≥4.136 is required for local DO-policy dev. `vite dev` cannot pull Cloudflare Registry images, so use a Dockerfile. (d) The vitest-pool-workers bundled wrangler cannot parse the new `containers` block, so give tests a config copy without it ([cloudflare/mcp-server-cloudflare#523](https://github.com/cloudflare/mcp-server-cloudflare/issues/523)). (e) At most 128 intercept entries (64 hostnames). (f) Outbound HTTP bodies through handlers are capped at **100 MiB**. (g) On the DO policy, the container runs in its DO's jurisdiction. |

### 1.1 Verified minimal template (DO Container API + FastAPI)
`wrangler.jsonc` (minimal subset; the full file is in §7):
```jsonc
{ "name": "ugecy", "main": "worker/index.ts", "compatibility_date": "2026-11-07", "compatibility_flags": ["nodejs_compat"],
  "observability": { "enabled": true },
  "containers": [{ "class_name": "AgentRuntime", "scheduling_policy": "durable_object",
                   "images": { "agent": { "dockerfile": "./services/agent/Dockerfile", "build_context": "./services/agent" } } }],
  "durable_objects": { "bindings": [{ "name": "AGENT_RUNTIME", "class_name": "AgentRuntime" }] },
  "exports": { "AgentRuntime": { "type": "durable-object", "storage": "sqlite" } } }   // `exports` replaces `migrations`; never use both
```
`worker/do/agent-runtime.ts`, following the official readiness and forwarding pattern:
```ts
import { DurableObject } from "cloudflare:workers";
const PORT = 8000, IDLE_MS = 15 * 60_000;
const VHOSTS = ["llm.internal", "bindings.internal", "state.internal", "events.internal", "higgsfield.internal"];
export class AgentRuntime extends DurableObject<Env> {
  private starting?: Promise<void>;
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    const c = ctx.container!;
    if (c.running) void ctx.blockConcurrencyWhile(() => c.setInactivityTimeout(IDLE_MS)); // timeout is lost on DO restart
  }
  async fetch(req: Request): Promise<Response> {            // SSE + WebSocket passthrough
    this.starting ??= this.ensureReady().finally(() => (this.starting = undefined));
    await this.starting;
    const url = new URL(req.url); url.protocol = "http:"; url.host = "container";
    const fwd = new Request(url, req); fwd.headers.delete("host");
    return this.ctx.container!.getTcpPort(PORT).fetch(fwd);
  }
  private async ensureReady() {
    const c = this.ctx.container!;
    if (!c.running) {
      c.start({ image: c.images.agent, instance: "standard-1", enableInternet: false,
                env: { UGECY_RUNTIME_ID: this.ctx.id.toString() }, labels: { app: "ugecy" } });
      const gw = this.ctx.exports.EgressGateway({ props: { runtimeId: this.ctx.id.toString() } }); // ctx.exports: default since compat 2025-11-17
      for (const h of VHOSTS) await c.interceptOutboundHttp(h, gw); // re-register for every new container
      this.ctx.waitUntil(c.monitor().catch((e) => console.error("agent container exited", e)));
    }
    await c.setInactivityTimeout(IDLE_MS);
    const port = c.getTcpPort(PORT);
    for (let i = 0; i < 150; i++) {                          // start() returns before the app is ready
      try { const r = await port.fetch("http://container/healthz", { signal: AbortSignal.timeout(1000) });
            await r.body?.cancel(); if (r.ok) return; } catch {}
      await scheduler.wait(200);
    }
    throw new Error("agent container not ready on :8000");
  }
}
```
`services/agent/Dockerfile` and `app/main.py`:
```dockerfile
FROM --platform=linux/amd64 python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY app ./app
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--timeout-graceful-shutdown","600"]
```
```python
import json
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse   # sse-starlette 3.7.0, fastapi 0.162.1, uvicorn 0.54.0
app = FastAPI()
@app.get("/healthz")
async def healthz(): return {"ok": True}
@app.post("/runs")                                  # one deep-agent turn, streamed as SSE
async def runs(req: Request):
    body = await req.json()
    async def gen():
        async for ev in run_agent(body):            # deepagents astream(..., stream_mode=["messages","updates","custom"])
            yield {"event": ev["type"], "data": json.dumps(ev)}
    return EventSourceResponse(gen(), ping=15)      # keepalive pings stop idle intermediaries from cutting the stream
```
Handle SIGTERM by letting uvicorn's graceful shutdown finish the current graph step. The checkpointer has already persisted state (§5).

## 2. How the Python container reaches Workers AI and bindings
| Option | Verdict |
|---|---|
| A. **Outbound intercept to `WorkerEntrypoint` (2026 native)**: `ctx.container.interceptOutboundHttp(host, fetcher)`, or `interceptOutboundHttps` (needs the ephemeral CA at `/etc/cloudflare/certs/cloudflare-containers-ca.crt`). The handler "run[s] on the same machine as the container", has **all bindings**, and keeps secrets out of the sandbox. With `enableInternet:false`, DNS resolves only intercepted hosts ([outbound-traffic](https://developers.cloudflare.com/containers/configuration/outbound-traffic/), [workers-connections](https://developers.cloudflare.com/containers/configuration/workers-connections/)) | **Recommended.** No shared secret, because intercepts are installed per container and carry `props`. Plain HTTP to `*.internal` avoids the TLS-interception CA dance. The handler upgrades to HTTPS. |
| B. Worker `/internal/*` route plus a shared secret | Works, but sends traffic over the public edge and puts a secret in the container. Use A instead. |
| C. Workers AI REST with a scoped token **inside** the container | Simplest, but the token sits in the sandbox and LLM-generated code could exfiltrate it. Reject. This **supersedes** the in-container `CF_AI_TOKEN` in DEEPAGENTS.md §9: keep its `ChatOpenAI` code and change `base_url`/`api_key`. |
| D. AI Gateway | This is not an alternative: it sits **behind** A (header `cf-aig-gateway-id`). |

`worker/egress/gateway.ts` (each concern in its own file, all under 500 lines):
```ts
import { WorkerEntrypoint } from "cloudflare:workers";
type P = { runtimeId: string };
export class EgressGateway extends WorkerEntrypoint<Env, P> {
  async fetch(req: Request) {
    const u = new URL(req.url);
    switch (u.hostname) {
      case "llm.internal": {                       // OpenAI wire format, streaming or not
        if (!/^\/v1\/(chat\/completions|embeddings)$/.test(u.pathname)) return new Response("no", { status: 404 });
        const thread = req.headers.get("x-ugecy-thread") ?? this.ctx.props.runtimeId;
        return fetch(`https://api.cloudflare.com/client/v4/accounts/${this.env.CF_ACCOUNT_ID}/ai${u.pathname}`, {
          method: "POST", body: req.body, headers: {
            "content-type": "application/json", authorization: `Bearer ${await this.env.CF_AI_TOKEN.get()}`,
            "cf-aig-gateway-id": this.env.AI_GATEWAY_ID, "x-session-affinity": thread,   // prefix-cache hits
            "cf-aig-metadata": JSON.stringify({ thread, runtime: this.ctx.props.runtimeId }),
            "cf-aig-max-attempts": "3", "cf-aig-backoff": "exponential" } });
      }
      case "bindings.internal": return bindingsApi(req, u, this.env, this.ctx.props); // narrow JSON RPC: d1/kv/vectorize/queue/stream/browser
      case "state.internal":    return stateApi(req, u, this.env, this.ctx.props);    // LangGraph checkpointer → DO SQLite (§5)
      case "events.internal":   return eventsApi(req, u, this.env);                   // push UI events to ChatSession DO
      case "higgsfield.internal": return vendor(req, u, "https://<higgsfield-api-host>", await this.env.HIGGSFIELD_API_KEY.get());
      default: return new Response("egress denied", { status: 403 });                 // audit this to Analytics Engine
    }
  }
}
```
Python side: `ChatOpenAI(model="@cf/zai-org/glm-5.3", base_url="http://llm.internal/v1", api_key="intercepted", default_headers={"x-ugecy-thread": tid}, use_responses_api=False, timeout=600)`. The OpenAI SDK requires a non-empty key. Every vendor SDK in the container needs a configurable base URL that points at `http://<vendor>.internal`. Export the `EgressGateway` class from the Worker entrypoint. An alternative LLM path is `env.AI.run(model, body, {gateway:{id}, extraHeaders})`, which needs no token, but the binding's SSE chunk shape for OpenAI-schema models is **[unverified]**. Spike it and keep REST as the default.

## 3. Workers AI and AI Gateway
**Endpoints.** REST `POST /accounts/{id}/ai/v1/chat/completions` and `/ai/v1/embeddings` work with the OpenAI SDK, and `/ai/v1/responses` works for GPT-OSS only. `/ai/run` and `/ai/run/@cf/...` are the native envelope. The binding `env.AI.run(model,{messages,tools,stream:true})` returns an SSE ReadableStream. Tokens need **Account › Workers AI › Read**. A token with only an AI Gateway permission gets 401/10000 ([rest-api](https://developers.cloudflare.com/ai-gateway/usage/rest-api/)). Model inputs follow the OpenAI shape: `tools`, `tool_choice`, `parallel_tool_calls` (default true), `response_format` (JSON schema), `stream`, `stream_options`, and `reasoning_effort`. To fail fast instead of queuing, send `options.rejectIfBusy`. Prefix caching triggers on the `x-session-affinity` header (or `extraHeaders` on the binding); keep system prompts and tools static and put timestamps last. Workers AI is GA. Pricing is $0.011 per 1k neurons, with 10k free per day. The async Batch API covers models flagged `async_queue`.

**Rate limits (critical).** Text generation is limited to 300 rpm, **but "paid models" are limited to 20 rpm per model per account** (50 rpm with prepaid AI Gateway credits and *Unified billing*). `glm-5.3` and `deepseek-v4.1-flash` are paid models ([limits](https://developers.cloudflare.com/workers-ai/platform/limits/)). Embeddings are limited to 3,000 rpm, ASR and image-to-text to 720 rpm.

| Use | Model (live catalog via API probe, 2026-11-07) | Context | $/M in·out (cached) | Notes |
|---|---|---|---|---|
| Orchestrator / planning | `@cf/zai-org/glm-5.3` | 1,048,576 | 1.40·4.40 (0.26) | Function calling, reasoning low/high/max (default max), zero data retention, **paid, 20 rpm** |
| Orchestrator alt / vision | `@cf/deepseek-ai/deepseek-v4.1-flash-1017` | 1,048,576 | 0.30·1.20 (0.006) | Function calling, vision, reasoning none–max, **paid, 20 rpm** |
| Subagents / bulk | `@cf/qwen/qwen3.8-27b` | 262,144 | 0.45·3.20 (0.05) | Function calling, vision, reasoning, 300 rpm |
| Cheap / fast tools | `@cf/zai-org/glm-4.7-flash` | 131,072 | 0.0605·0.40 | Function calling, 300 rpm |
| Embeddings | `@cf/baai/bge-m3` (multilingual, 1024-d), `@cf/qwen/qwen3-embedding-0.6b` (8k ctx) | — | 0.0118 | Also `bge-small/base/large-en-v1.5` (384/768/1024-d, 512 tok). Reranker: `@cf/baai/bge-reranker-base` |
| Speech-to-text | `@cf/openai/whisper-large-v3-turbo` ($0.000513/min), `@cf/deepgram/nova-3` ($0.0052/min), `@cf/deepgram/flux` (WebSocket) | — | — | Transcribe trending UGC audio |
| Vision captioning | deepseek-v4.1-flash, qwen3.8-27b, `@cf/moondream/moondream3.1-9B-A2B`, `@cf/google/gemma-4-26b-a4b-it` | — | — | Frame or thumbnail analysis |
| TTS (later) | `@cf/deepgram/aura-2-en` / `aura-2-es` | — | $0.03/1k chars | Voiceover drafts |

**Do not use the models deprecated on 2026-11-20** (they return 410/5028): glm-5.3-flash, glm-5.2, kimi-k2.6/k2.7-code, deepseek-v4-flash-0731/v4-pro-0813, qwen3-30b-a3b, qwq-32b, whisper-tiny-en, llava-1.5, melotts, and embeddinggemma-300m ([changelog](https://developers.cloudflare.com/changelog/post/2026-11-05-planned-model-deprecations/)).

**AI Gateway** (create the gateway `ugecy`; GET `/ai-gateway/gateways` returned 0):
- **Authentication is mandatory for new gateways (2026-11-03) and cannot be turned off.** REST callers send the API token in `Authorization`. Bindings are pre-authenticated. AI Gateway tokens are account-scoped and cannot be limited to one gateway.
- Features: logs (gateways created after 2026-09-24 use Workers Logs pricing; use `cf-aig-collect-log-payload:false` for sensitive payloads), cost analytics, custom metadata `cf-aig-metadata`, exact-match caching (`cf-aig-cache-ttl`, `cf-aig-skip-cache`; useless for agent chat, useful for embeddings and classification), fixed or sliding rate limits, retries (`cf-aig-max-attempts` ≤5, `cf-aig-retry-delay`, `cf-aig-backoff`), `cf-aig-request-timeout` (measured to the first byte, so streaming is fine), **model aliases** (`custom/<name>`: an ordered fallback pool or smart routing, ≤50 models, ≤100 aliases, launched 2026-11-04), dynamic routes, spend limits, guardrails, DLP, OTel export, and Logpush. `/compat/chat/completions` and the Universal endpoint are deprecated for new single-model integrations.
- Wiring for Ugecy: create aliases `custom/ugecy-orchestrator` = [glm-5.3 → deepseek-v4.1-flash → qwen3.8-27b] and `custom/ugecy-worker` = [qwen3.8-27b → glm-4.7-flash]. Each paid model has its own 20 rpm budget, so the fallback chain absorbs 429s. Calling aliases through `/ai/v1/chat/completions` is **[unverified]**; the docs show `/ai/run`. Load prepaid credits for 50 rpm.

## 4. Frontend hosting
**Recommendation: Workers Static Assets in the same `ugecy` Worker, built with Vite 8 + `@cloudflare/vite-plugin@1.67` (v1 stable; v2 is in beta) + React 19 + shadcn.** Scaffold with `pnpm create cloudflare@latest ugecy --framework=react`. `vite dev` runs the Worker in workerd with real bindings, including local Docker containers.
```jsonc
"assets": { "not_found_handling": "single-page-application", "binding": "ASSETS",
            "run_worker_first": ["/api/*", "/agents/*", "/oauth/*", "/webhooks/*"] }
```
- SPA mode serves `index.html` for navigation requests (`Sec-Fetch-Mode: navigate`). **OAuth callbacks for social accounts are navigations**, so they must be listed in `run_worker_first` or the SPA will swallow them ([SPA docs](https://developers.cloudflare.com/workers/static-assets/routing/single-page-application/)). Asset requests are free and do not invoke the Worker.
- **Access caveat.** A Worker with static assets runs behind an internal router, so `ctx.access` is **not** passed through. Verify the `Cf-Access-Jwt-Assertion` header yourself (use `jose` against `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` and check `aud`) ([cloudflare-access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)).
- workers.dev runs Browser Integrity Check, which cannot be turned off. Clients with default library user agents (python-urllib) get error 1010. Vendor webhooks are safer on a custom domain.

## 5. Data and async services (fit for Ugecy)
| Service | Ugecy role | v1? | Key limits / notes |
|---|---|---|---|
| **D1** `ugecy-db` | System of record: workspaces, campaigns, posts, connected accounts (tokens AES-GCM-encrypted with `TOKEN_ENC_KEY`), approvals, **append-only audit log**, jobs | v1 | 10 GB per DB, 2 MB per row, 30 s per query, 100 bound params, 1,000 queries per invocation, 30-day Time Travel. Use `migrations_dir: "migrations"`, then `wrangler d1 migrations create ugecy-db <name>` and `wrangler d1 migrations apply ugecy-db --remote` |
| **DO SQLite** `AgentRuntime` / `ChatSession` | LangGraph checkpoints and writes, per-thread messages and event log, UI state | v1 | 10 GB per object, 8 MB per row, 30-day point-in-time recovery, alarms, hibernating WebSockets (≤32 MiB per message). Checkpointer: a custom async `BaseCheckpointSaver` over `http://state.internal` → AgentRuntime DO SQLite, which sits next to its container. This is **all-Cloudflare**. DEEPAGENTS.md prefers Postgres (Neon) + `AsyncPostgresStore`; if latency or effort disappoint, the fallback is Postgres via Hyperdrive. D1 saver (`langgraph-checkpoint-cloudflare-d1`) is a third option. Decide in Phase 0 |
| **KV** `ugecy-cache` | Feature flags, OAuth `state` nonces (TTL), small artifacts ≤25 MiB, research cache | v1 | Eventually consistent (about 60 s). 1 write per second per key |
| **Queues** `ugecy-jobs` + `ugecy-jobs-dlq` | Publish attempts, media ingest, crawl fan-out, metrics pulls | v1 | 128 KB per message, ≤100 per batch, `max_retries` ≤100, `retry_delay`, `delaySeconds` ≤24 h, consumer wall time ≤15 min, retention ≤14 days. Do not touch the existing `resspark-jobs*` queues |
| **Workflows** `ugecy-campaign`, `ugecy-publish` | campaign → research → script → generate → **approve** → schedule → publish → measure | v1 | `waitForEvent` timeout 1 s–365 d (default 24 h), event type `[A-Za-z0-9_-]` (no dots), `sleepUntil` ≤365 d, 10k steps (configurable to 25k), CPU 30 s per step (configurable to 5 min) with unlimited wall time, ≤1 MiB per step result or event, 1 GB state, retention 7 d (≤30 d), `rollback` handlers, `schedules` (cron) |
| **Durable Objects** | `AgentRuntime` (container owner, one per workspace), `ChatSession` (Agent, one per thread), later `DeviceSession` (serialised Glasshand actions and alarms) | v1 | CPU 30 s per request (configurable to 5 min). Automatic retries for DO calls (2026-11-05) |
| **Cron** | Post metrics sync and research refresh | v1 | `triggers.crons`, or Workflow `schedules` |
| **Vectorize** `ugecy-memory` | Semantic memory and pattern library (bge-m3, 1024-d, cosine) | v1 | ≤1536 dimensions, 10 KiB metadata, topK 50 with metadata, 10 metadata indexes, 50k namespaces (namespace = workspace). Not auto-provisioned: `wrangler vectorize create ugecy-memory --dimensions=1024 --metric=cosine` |
| **Analytics Engine** `ugecy_events` | Tool-call, egress-deny, cost, and publish-outcome metrics | v1 | `env.METRICS.writeDataPoint({blobs,doubles,indexes})`. Querying needs Account Analytics Read |
| **Browser Run** (renamed from Browser Rendering) | Research scraping: `/markdown`, `/content`, `/json` (AI extraction), `/links`, `/screenshot`, `/snapshot`, async `/crawl` jobs (≤7 days, results kept 14 days, per-URL `outcome` and `robots` diagnostics) | v1 | Binding `env.BROWSER.quickAction("markdown",{url})`. Paid plan: 10 browser-hours per month included, then $0.09/h; 30 Quick-Action requests per second; 60 s browser timeout. The REST `/crawl` endpoint needs a "Browser Run Edit" token. Respect robots.txt and the platforms' terms of service |
| **Stream** (subscribed) | Higgsfield videos: `env.STREAM.upload(url,{meta})` (copy-from-URL), MP4 downloads for API publishing, HLS preview in the asset sidebar. **WebRTC WHIP ingest / WHEP playback is GA** (billed since 2026-10-15) and could be the iPhone-screen sink. The WHIP URL is a credential | v1 / later (WHIP) | Probe: 0 videos, storage limit reads 0 (see §8) |
| **Images** (subscribed) | Still and thumbnail storage via the binding ("Manage hosted images with Workers"), variants, signed URLs | v1 | Probe: count allowed = 0 (see §8) |
| **Secrets Store** (open beta) | Vendor keys: `CF_AI_TOKEN`, `HIGGSFIELD_API_KEY`, `FIRECRAWL_API_KEY`, OAuth client secrets | v1 | Quota 100 secrets (probe). Binding `secrets_store_secrets`, read with `await env.X.get()` |
| **Access** (Zero Trust) | Protect the app (operator login) and bypass `/webhooks/*` | v1 (needs dashboard enablement) | Probe: `access.api.error.not_enabled`. Enable Zero Trust (free tier) first. Workers.dev one-click Access is available after that |
| **Turnstile** | Only if a non-Access login or public form appears | later | Widgets API reachable |
| **R2** | Media originals, export bundles, FUSE mount | **later, blocked**: enable in dashboard | 403 10042 "Please enable R2 through the Cloudflare Dashboard" |
| Agent Memory (private beta), AI Search, Artifacts (git-versioned files: a good fit for versioned scripts and briefs) | Managed memory / RAG / versioned agent files | later | Check access before planning |

Workflow sketch (`worker/workflows/publish.ts`):
```ts
export class PublishWorkflow extends WorkflowEntrypoint<Env, { postId: string; publishAt?: string }> {
  async run(ev: WorkflowEvent<{ postId: string; publishAt?: string }>, step: WorkflowStep) {
    const r = { limit: 5, delay: "1 minute", backoff: "exponential" } as const;
    const media = await step.do("render", { retries: r, timeout: "30 minutes" }, () => runtimeJob(this.env, "/jobs/render", ev.payload));
    const vid = await step.do("ingest", () => this.env.STREAM.upload(media.url, { meta: { postId: ev.payload.postId } }).then(v => ({ uid: v.uid })));
    await step.do("ask-approval", () => markPending(this.env.DB, ev.payload.postId, vid.uid));   // UI shows it in Approvals
    const d = await step.waitForEvent<{ approved: boolean; by: string }>("operator approval", { type: "approval", timeout: "7 days" });
    if (!d.payload.approved) return step.do("rejected", () => audit(this.env.DB, ev.payload.postId, "rejected", d.payload.by));
    if (ev.payload.publishAt) await step.sleepUntil("scheduled slot", new Date(ev.payload.publishAt));
    const receipt = await step.do("publish", { retries: r }, () => runtimeJob(this.env, "/jobs/publish", { ...ev.payload, vid }));
    await step.do("audit", () => audit(this.env.DB, ev.payload.postId, "published", receipt));
  }
} // approve: POST /api/approvals/:id → (await env.PUBLISH_WF.get(instId)).sendEvent({ type: "approval", payload }) + audit row
```
`runtimeJob` calls `env.AGENT_RUNTIME.getByName(ws).fetch(...)`, which wakes the container. Python owns the domain logic, while Workflows owns durability, timing, and approvals. A timed-out `waitForEvent` throws, so catch it and mark the post expired.

## 6. Headless deploy: token permissions and live probe (2026-11-07, GET only)
Token is `active`, never expires. It cannot read its own policies (`/user/tokens/{id}` returns 9109), so **write scopes cannot be verified read-only**. `/memberships` and `/user` return 403, so always export `CLOUDFLARE_ACCOUNT_ID` for wrangler (already set). The account has Workers Paid and Images+Stream basic. Subdomain is `zh-a16`. There is one zone, `resspark.com` (Free). Existing: Worker `resspark` and queues `resspark-jobs` / `resspark-jobs-dlq` (do not touch).
| Feature | Probe endpoint | Result | Deploy needs (Account scope unless noted) |
|---|---|---|---|
| Workers scripts / subdomain / custom domains | `/workers/scripts`, `/workers/subdomain`, `/workers/domains` | ✅ 200 (1 script) / ✅ / ✅ (0) | Workers Scripts Edit, Workers Tail Read |
| Durable Objects namespaces | `/workers/durable_objects/namespaces` | ✅ 200 (0) | (Workers Scripts Edit) |
| Containers apps / registry / limits | `/containers/applications`, `/containers/registries`, `/containers/me` | ✅ 200 (0 apps), registry.cloudflare.com present | Containers Edit (app + image push) |
| D1 | `/d1/database` | ✅ 200 (0) | D1 Edit |
| KV | `/storage/kv/namespaces` | ✅ 200 (0) | Workers KV Storage Edit |
| Queues | `/queues` | ✅ 200 (2 resspark queues) | Queues Edit |
| Workflows | `/workflows` | ✅ 200 (0) | (Workers Scripts Edit) |
| Vectorize | `/vectorize/v2/indexes` | ✅ 200 (0) | Vectorize Edit |
| Workers AI | `/ai/models/search` | ✅ 200 (73 models) | Workers AI Read (also the runtime `CF_AI_TOKEN`; give that token *only* this) |
| AI Gateway | `/ai-gateway/gateways` | ✅ 200 (0); `default` returns 404 | AI Gateway Edit |
| Browser Run | `/browser-rendering/devtools/session` | ✅ 200 `[]` | Browser Run Edit (REST `/crawl`); the binding needs none |
| Stream / live inputs | `/stream`, `/stream/live_inputs`, `/stream/keys` | ✅ 200 (0 / 0) | Stream Edit |
| Images | `/images/v1`, `/images/v1/stats`, `/images/v2` | ✅ 200 (allowed: 0) | Cloudflare Images Edit |
| Secrets Store | `/secrets_store/stores`, `/quota` | ✅ 200 (0 stores, quota 100) | Secrets Store Edit |
| Pages | `/pages/projects` | ✅ 200 (0); not needed | — |
| Turnstile | `/challenges/widgets` | ✅ 200 (0) | Turnstile Edit (later) |
| Hyperdrive, Pipelines, AI Search, Realtime/Calls, Logpush, Workers Builds tokens | various | ✅ 200 (all empty) | only if adopted |
| Analytics Engine SQL | `/analytics_engine/sql` | ⚠️ 400 on GET (the endpoint is POST-only; not probed) | Account Analytics Read |
| **R2** | `/r2/buckets` | ❌ 403 `10042 Please enable R2 through the Cloudflare Dashboard` | Workers R2 Storage Edit (after enabling) |
| **Access / Zero Trust** | `/access/apps`, `/access/organizations` | ❌ 403 `access.api.error.not_enabled` | Access: Apps and Policies Edit (after enabling Zero Trust) |
| Zone DNS (for custom domain) | `/zones/{id}/dns_records` | ❌ 403 10000 (Workers routes read ✅) | Zone Read, DNS Edit, Workers Routes Edit, *only if* using `*.resspark.com` |
| Workers for Platforms | `/workers/dispatch/namespaces` | ❌ 403 10121 (not purchased) | not needed |
Recommended CI token = the Account permissions above (Edit level). Create a second, runtime-only token with **Workers AI Read** and store it as `CF_AI_TOKEN` in Secrets Store.

## 7. Recommendation for Ugecy
**Resources (v1):** Worker `ugecy` · Container app `ugecy-agentruntime` (DO policy, image `agent`, standard-1) · DOs `AgentRuntime`, `ChatSession` · D1 `ugecy-db` · KV `ugecy-cache` · Queues `ugecy-jobs`, `ugecy-jobs-dlq` · Workflows `ugecy-campaign`, `ugecy-publish` · Vectorize `ugecy-memory` (1024, cosine) · AI Gateway `ugecy` (auth on, logs on, payload logging off for OAuth-bearing calls, aliases `custom/ugecy-orchestrator` and `custom/ugecy-worker`, spend limit) · Analytics Engine `ugecy_events` · Secrets Store `ugecy` · Browser Run, Stream, and Images bindings.
**Later:** R2 `ugecy-media` (once enabled), Access app + bypass `/webhooks/*`, `DeviceSession` DO + Stream WebRTC live input (Glasshand), snapshots for warm agent workspaces, Agent Memory / AI Search / Artifacts, custom domain (for example `app.<domain>`) for webhooks, TikTok URL-prefix verification, and avoiding the workers.dev Browser Integrity Check, staging env `--env staging`.
```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "ugecy", "main": "worker/index.ts",
  "compatibility_date": "2026-11-07", "compatibility_flags": ["nodejs_compat"],
  "workers_dev": true, "upload_source_maps": true,
  "observability": { "enabled": true, "head_sampling_rate": 1 },
  "assets": { "not_found_handling": "single-page-application", "binding": "ASSETS",
              "run_worker_first": ["/api/*", "/agents/*", "/oauth/*", "/webhooks/*"] },   // directory set by the vite plugin build
  "vars": { "CF_ACCOUNT_ID": "<ACCOUNT_ID>", "AI_GATEWAY_ID": "ugecy", "WORKSPACE_ID": "default",
            "ACCESS_TEAM_DOMAIN": "<team>.cloudflareaccess.com", "ACCESS_AUD": "<aud-tag>" },
  "secrets": { "required": ["TOKEN_ENC_KEY"] },                      // deploy fails if missing
  "secrets_store_secrets": [
    { "binding": "CF_AI_TOKEN", "store_id": "<STORE_ID>", "secret_name": "ugecy-cf-ai-token" },
    { "binding": "HIGGSFIELD_API_KEY", "store_id": "<STORE_ID>", "secret_name": "ugecy-higgsfield" },
    { "binding": "FIRECRAWL_API_KEY", "store_id": "<STORE_ID>", "secret_name": "ugecy-firecrawl" } ],
  "ai": { "binding": "AI" },
  "browser": { "binding": "BROWSER" },
  "stream": { "binding": "STREAM" },
  "images": { "binding": "IMAGES" },
  "d1_databases": [{ "binding": "DB", "database_name": "ugecy-db", "database_id": "<from bootstrap>", "migrations_dir": "migrations" }],
  "kv_namespaces": [{ "binding": "KV", "id": "<from bootstrap>" }],
  "vectorize": [{ "binding": "MEMORY", "index_name": "ugecy-memory" }],
  "analytics_engine_datasets": [{ "binding": "METRICS", "dataset": "ugecy_events" }],
  "queues": {
    "producers": [{ "binding": "JOBS", "queue": "ugecy-jobs" }],
    "consumers": [{ "queue": "ugecy-jobs", "max_batch_size": 10, "max_batch_timeout": 5, "max_retries": 5,
                    "retry_delay": 60, "max_concurrency": 5, "dead_letter_queue": "ugecy-jobs-dlq" }] },
  "workflows": [
    { "binding": "CAMPAIGN_WF", "name": "ugecy-campaign", "class_name": "CampaignWorkflow" },
    { "binding": "PUBLISH_WF",  "name": "ugecy-publish",  "class_name": "PublishWorkflow" } ],
  "containers": [{ "class_name": "AgentRuntime", "scheduling_policy": "durable_object",
                   "images": { "agent": { "dockerfile": "./services/agent/Dockerfile", "build_context": "./services/agent" } },
                   "observability": { "enabled": true } }],
  "durable_objects": { "bindings": [
    { "name": "AGENT_RUNTIME", "class_name": "AgentRuntime" },
    { "name": "ChatSession", "class_name": "ChatSession" } ] },               // Agents SDK route: /agents/chat-session/<threadId>
  "exports": {
    "AgentRuntime": { "type": "durable-object", "storage": "sqlite" },
    "ChatSession":  { "type": "durable-object", "storage": "sqlite" } },
  "triggers": { "crons": ["17 */6 * * *"] }                                   // metrics sync and research refresh
}
```
`worker/index.ts` exports `default` (fetch / queue / scheduled), `AgentRuntime`, `ChatSession`, `EgressGateway`, `CampaignWorkflow`, and `PublishWorkflow`. The `default.fetch` order is: verify the Access JWT, then `routeAgentRequest(req, env)` (Agents SDK), then the Hono `/api/*` router, then the `/webhooks/*` router (HMAC verification, no Access).

**Request flow**
```
Browser (React SPA from Static Assets; useAgent WS)
  │  https://ugecy.zh-a16.workers.dev  ──► [Access (once enabled)]  ──► Worker `ugecy` default.fetch
  │       ├─ /assets, SPA routes ............ served free by Static Assets
  │       ├─ /agents/chat-session/:thread ... WS ─► ChatSession DO (Agent: hibernating WS, state sync, msg log)
  │       │        send(msg) ─► AGENT_RUNTIME.getByName(ws).fetch("/runs")  (SSE back, fanned out to WS + state)
  │       ├─ /api/* (Hono) .................. D1 / KV / Workflows.create|sendEvent(approval) / Stream / Images
  │       └─ /webhooks/* .................... vendor callbacks ─► Workflow.sendEvent / Queue
  ▼
AgentRuntime DO (SQLite: LangGraph checkpoints) ── ctx.container.start(image "agent", standard-1, enableInternet:false)
  └─ Python container :8000 (FastAPI + deepagents + LangGraph)
       ├─ http://llm.internal/v1/chat/completions ─┐
       ├─ http://state.internal/...  (checkpointer)│  intercepted on-host ─► EgressGateway (WorkerEntrypoint, has env + secrets)
       ├─ http://bindings.internal/... (d1/kv/vec) │      ├─► api.cloudflare.com/ai/v1  ─► AI Gateway `ugecy` ─► Workers AI (GLM-5.3 …)
       ├─ http://events.internal/... (UI events)   │      ├─► AgentRuntime/ChatSession DO RPC, D1, KV, Vectorize, Queues, Stream, Browser Run
       └─ http://higgsfield.internal/...           ┘      └─► https://<vendor> + injected key   (all else: 403 + METRICS)
Workflows (campaign/publish: step.do → waitForEvent(approval) → sleepUntil → publish) ─► Queue ugecy-jobs ─► consumer ─► DLQ
```
**Parallel work packages** (each file ≤500 lines): WP1 `wrangler.jsonc` + `scripts/bootstrap.sh` (create D1, KV, queues, Vectorize, AI Gateway, Secrets Store; idempotent `wrangler ... create`) · WP2 `worker/do/agent-runtime.ts` · WP3 `worker/egress/*` (gateway, llm, bindings, state, events, vendors) · WP4 `worker/do/chat-session.ts` + event protocol shared with SPA (`shared/events.ts`) · WP5 `worker/workflows/*` + `/api/approvals` · WP6 `worker/queues/jobs.ts` + DLQ replay · WP7 `migrations/0001_init.sql` + audit helpers · WP8 `worker/assets/{stream,images,kv}.ts` · WP9 `worker/auth/access.ts` (JWT) + interim auth · WP10 `services/agent` (Dockerfile, FastAPI, `cf_clients.py` for `*.internal`, DO-SQLite checkpointer). **TS exception:** the edge layer must be TypeScript, because the Containers DO API, Agents SDK, and Vite plugin are TS-first. Record it as an approved exception under engineering rule 4, and keep all domain logic in Python.

**Headless runbook:** `export CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN` → `pnpm i` (wrangler ^4.158.0, @cloudflare/vite-plugin ^1.67.0, agents ^0.33.0, hono ^4.13) → `scripts/bootstrap.sh` → `wrangler d1 migrations apply ugecy-db --remote` → `wrangler secret put TOKEN_ENC_KEY` → `pnpm build && wrangler deploy` (needs the Docker daemon; first deploy takes minutes) → `wrangler containers list` → smoke-test `/api/health` and `/agents/chat-session/test`. CI: Workers Builds on the production branch must run `wrangler deploy`, not `versions upload`.

## 8. Open questions and risks
1. **The DO scheduling policy is beta, and `default` is deprecated.** Keep container control in one file (WP2) so an API change stays local. Re-check docs before each phase.
2. **Paid-model 20 rpm per model.** A deep agent with subagents will hit 429s. Mitigate with alias fallback across models, subagents on qwen3.8/glm-4.7-flash (300 rpm), prepaid AI Gateway credits (50 rpm), and the custom-limits form. *Decision for the user: load AIG credits?*
3. **Binding SSE shape and aliases on `/ai/v1/chat/completions` are [unverified].** Phase-0 spike: one streamed tool call through `llm.internal` with glm-5.3 and `custom/ugecy-orchestrator`, checked with LangChain `ChatOpenAI`.
4. **Checkpointer choice.** Options are the custom DO-SQLite saver (all-Cloudflare, more code), Postgres + Hyperdrive (external DB, proven saver per DEEPAGENTS.md), or D1 saver (REST latency). The user's "everything on Cloudflare" rule argues for the DO-SQLite saver, but it needs tests (DeltaChannel history reads).
5. **R2 disabled.** Stream and Images cover delivery. Originals over 25 MiB that are not video have no home. Several social APIs pull media from a URL (TikTok PULL_FROM_URL requires a **verified domain prefix**), so `customer-*.cloudflarestream.com` URLs may be rejected. That needs a custom domain proxy or R2 custom domain. *Ask the user to enable R2 and pick a domain.*
6. **Images `allowed: 0` and Stream `totalStorageMinutesLimit: 0`** in the probes. These may be plan fields or a sign that storage is not provisioned. Verify with one upload in Phase 0.
7. **Access is not enabled.** Zero Trust onboarding is a manual dashboard step and may ask for a payment method. Until then, use an interim auth gate: a long random operator bearer token in a cookie, set through a one-time login link. Webhooks need an Access bypass policy by path.
8. **Container eviction.** Container ID changes and SIGTERM-on-host-maintenance mean every LangGraph step must checkpoint, runs must resume by `thread_id`, and Workflows must call idempotent `/jobs/*` endpoints with an idempotency key.
9. **Egress limits.** Outbound bodies are capped at 100 MiB per request, so social video uploads must use chunked or resumable APIs (or run in Worker Queue consumers with Stream MP4 URLs). There are 64 hostname intercepts at most. Every vendor SDK needs a base URL override.
10. **Tooling.** vitest-pool-workers cannot parse the new `containers` block, so use a test config without containers. Local Linux rootful Docker has no FUSE (irrelevant for v1). The 64-character hostname gotcha applies.
11. **Token scopes are unknown.** Write permissions are unverified. DNS, Access, and R2 are certainly missing. Create the CI token from the §6 table before the first deploy.
12. **Cost and pricing changes.** Container logs move to Observability pricing on 2026-12-01. AI Search billing starts 2026-12-01. Models deprecated on 2026-11-20 must never appear in config.
13. **iPhone live view.** Stream WebRTC WHIP needs Glasshand (or a companion) to emit WHIP. If it emits only frames or WebSocket, use the Realtime SFU or a WS relay through `DeviceSession` DO instead. See INTEGRATIONS.md.
14. **Compliance.** Browser Run crawling must honour robots.txt and the platforms' terms of service (crawl results now report `robots_disallowed`). No account creation, warming, or evasion features.

Sources (all fetched 2026-11-07): developers.cloudflare.com/containers/{platform/limits,platform/pricing,faq,api,api/durable-object-container,api/container-class,configuration/{scheduling-policy,outbound-traffic,workers-connections,environment-variables,wrangler},guides/{deploy,local-dev,image-management},examples/{websocket,container-backend}} · workers/wrangler/configuration · workers/static-assets/routing/single-page-application · workers/configuration/{cloudflare-access,routing/workers-dev} · workers/platform/limits · workers-ai/{configuration/open-ai-compatibility,platform/limits,platform/pricing,features/prompt-caching,models/glm-5.3,models/deepseek-v4.1-flash-1017} · ai-gateway/{usage/rest-api,usage/worker-binding-methods,usage/providers/workersai,usage/chat-completion,configuration/{authentication,request-handling},features/{caching,routing/model-aliases}} · workflows/{build/events-and-parameters,build/workers-api,reference/limits} · queues/platform/limits · d1/platform/limits · durable-objects/{platform/limits,reference/durable-objects-migrations} · vectorize/platform/limits · browser-run/{limits,pricing,quick-actions/crawl-endpoint,quick-actions/markdown-endpoint} · stream/{uploading-videos/upload-via-link,webrtc,manage-video-library/bindings} · secrets-store/integrations/workers · agents/agent-class/{state,routing} · fundamentals/api/reference/permissions · changelog (2026-04-13 GA, 2026-09-30 DO policy, 2026-11-03 AIG auth, 2026-11-04 aliases, 2026-11-05 deprecations) · blog.cloudflare.com/faster-agent-sandboxes · npm/PyPI registries for versions.

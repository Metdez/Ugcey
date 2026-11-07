# Internal API: Python agent container ↔ Cloudflare Worker

The Python container runs with `enableInternet: false`. The only network paths it has are the HTTP virtual hosts below. The `AgentRuntime` Durable Object intercepts each one (`ctx.container.interceptOutboundHttp(host, EgressGateway)`), and the `EgressGateway` `WorkerEntrypoint` in `worker/egress/` handles the request. The gateway holds every binding and secret, so **the container never sees a credential.**

In local development (`UGECY_INTERNAL_MODE=local`), the Python `ugecy.internal` client replaces each host with the local fallback listed below. This lets the backend run with `uv run uvicorn ugecy.main:app` and no Worker.

All requests are `POST` with JSON (except the vendor proxies and llm). Responses are JSON. Errors are non-2xx with `{"error": {"code", "message"}}`. Binary values travel as base64 strings (`*_b64`).

| Host | Purpose | Edge implementation | Local fallback |
|---|---|---|---|
| `llm.internal` | OpenAI-compatible LLM + embeddings | `env.AI.run()` (Workers AI binding, no token) | `https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/v1` with `CLOUDFLARE_API_TOKEN` |
| `state.internal` | KV blobs for LangGraph checkpointer and store mirrors | `AgentRuntime` DO SQLite | SQLite file `.ugecy/state.db` (or memory in tests) |
| `bindings.internal` | D1, Browser Run, Vectorize, Stream, Workflows, metrics | Worker bindings | SQLite `.ugecy/app.db`, httpx fetch, in-memory vectors, no-ops |
| `higgsfield.internal` | Higgsfield REST passthrough | `https://api.higgsfield.ai` + `Authorization: Key ${HF_KEY}` | direct to `https://api.higgsfield.ai` with `HF_KEY` / `HF_API_KEY_SECRET` |
| `firecrawl.internal` | Firecrawl v2 REST passthrough (optional) | `https://api.firecrawl.dev` + `Authorization: Bearer ${FIRECRAWL_API_KEY}` | direct with `FIRECRAWL_API_KEY` |
| `glasshand.internal` | Glasshand REST passthrough (optional) | `https://api.glasshand.com` + bearer from stored device-flow token | direct |

A vendor host whose secret is missing returns `503 {"error":{"code":"not_configured"}}`, and the Python provider then falls back to **mock mode**.

## llm.internal

- `POST /v1/chat/completions`: an OpenAI Chat Completions body (`model`, `messages`, `tools`, `tool_choice`, `stream`, `stream_options`, `reasoning_effort`, `chat_template_kwargs`, `max_tokens`, `temperature`).
  - The gateway calls `env.AI.run(body.model, body_without_model, { gateway: { id: env.AI_GATEWAY_ID } })`. It omits `gateway` when `AI_GATEWAY_ID` is unset.
  - When `stream: true`, it returns `text/event-stream` and pipes the binding's SSE through. Drop any `data:` line whose JSON has no `choices` key (Workers AI appends `{"response":"","usage":...}`), and keep `data: [DONE]`.
  - When `stream: false`, it returns the `chat.completion` JSON object.
  - Model allowlist: `@cf/zai-org/glm-5.3`, `@cf/zai-org/glm-4.7-flash`, `@cf/deepseek-ai/deepseek-v4.1-flash-1017`, `@cf/qwen/qwen3.8-27b`, `@cf/openai/gpt-oss-120b`, `@cf/qwen/qwen3-embedding-0.6b`, `@cf/baai/bge-m3`. Anything else returns 400.
- `POST /v1/embeddings` takes `{model, input: string|string[]}` and returns `{data:[{embedding:number[], index}], model}`.

## state.internal (namespaced KV, values are bytes)

| Path | Body | Response |
|---|---|---|
| `/kv/get` | `{ns, prefix, after?}` | `{items:[{key, value_b64}], next}`: one page (≤ ~2 MB) of keys > `after`, sorted; repeat with `after=next` until `next` is null |
| `/kv/put` | `{ns, items:[{key, value_b64}]}` | `{ok:true, count}` (upsert, atomic per call) |
| `/kv/delete` | `{ns, prefix}` | `{ok:true, deleted}` |

Edge: SQLite table `kv(ns TEXT, key TEXT, value BLOB, updated_at INTEGER, PRIMARY KEY(ns, key))` in the `AgentRuntime` DO. The gateway reaches it with `env.AGENT_RUNTIME.get(idFromString(props.runtimeId))` RPC methods `kvGet/kvPut/kvDelete`. Namespaces in use:
- `ckpt:<thread_id>` (checkpointer mirror)
- `store` (LangGraph Store mirror: memories, skills)

## bindings.internal

| Path | Body | Response | Edge binding |
|---|---|---|---|
| `/d1/query` | `{sql, params: any[]}` | `{results: object[], meta:{changes, last_row_id}}` | `env.DB.prepare(sql).bind(...params).all()` |
| `/d1/batch` | `{statements:[{sql, params}]}` | `{results: object[][]}` | `env.DB.batch(...)` |
| `/browser/markdown` | `{url}` | `{url, title, markdown}` (markdown truncated to 60k chars) | Browser Run quick action `markdown` (binding `BROWSER`); 502 on failure |
| `/vectors/upsert` | `{namespace, items:[{id, text, metadata}]}` | `{ok:true, count}` | embed with `@cf/qwen/qwen3-embedding-0.6b` → `env.MEMORY.upsert` |
| `/vectors/query` | `{namespace, text, top_k}` | `{matches:[{id, score, metadata}]}` | embed → `env.MEMORY.query(vec, {topK, namespace, returnMetadata:"all"})` |
| `/media/ingest` | `{asset_id, url, kind}` | `{asset_id, stream_uid?, playback_url?, thumbnail_url?}` | videos go to `env.STREAM` copy-from-URL. Images return the original URL (R2/Images later) |
| `/publish/schedule` | `{post_id, publish_at?: ISO}` | `{workflow_id}` | `env.PUBLISH_WF.create({id: post_id, params})` |
| `/metrics` | `{event, blobs: string[], doubles: number[]}` | `{ok:true}` | `env.METRICS.writeDataPoint` |

The D1 schema lives in `migrations/0001_init.sql`. It is applied with `wrangler d1 migrations apply ugecy-db --remote`, and the Python local SQLite fallback runs the same file. Tables: `threads`, `audit`, `assets`, `posts`, `accounts`, `approvals`, all columns matching `packages/contracts/src/models.ts`. JSON-valued fields are TEXT columns holding JSON.

## Worker → container (public API proxy)

The Worker forwards `/api/*`, except `/api/edge/*`, to `env.AGENT_RUNTIME.getByName("default").fetch(req)`. That DO starts the container if needed, then proxies to `http://container:8000` with the same path. SSE streams pass through unbuffered. Workflows call container jobs at `POST http://container:8000/jobs/<name>` (for example `/jobs/publish`) with an `Idempotency-Key` header.

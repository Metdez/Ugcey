# 02-10 SUMMARY: edge async + data layer

## Files created
- worker/egress/bindings.ts (handleBindings: d1 query/batch, browser/markdown, vectors upsert/query, media/ingest, publish/schedule, metrics)
- worker/egress/bindings-guards.ts (HttpError, SQL guard, public-URL guard, body guards)
- worker/workflows/publish.ts (PublishWorkflow)
- worker/queues/consumer.ts (handleQueue)
- worker/test/bindings.test.ts (24 tests)
- scripts/bootstrap.sh, scripts/deploy.sh, scripts/render-config.mjs (JSONC strip + D1/KV id fill; new, small helper)

## Exported interfaces
- `handleBindings(req, url, env, props): Promise<Response>` (exact plan signature, 4 args)
- `PublishWorkflow`, `handleQueue(batch, env)`

## Tests
- `apps/web/node_modules/.bin/vitest run --root worker test/bindings`: 24 passed. (vitest is not a root dep; `pnpm exec vitest` at root does not resolve.)
- `bash -n scripts/*.sh`: ok. shellcheck not installed.
- `tsc -p worker/tsconfig.json --noEmit`: my files clean. Remaining errors belong to others (below).
- bootstrap.sh/deploy.sh NOT run.

## Docs findings (differences from CLOUDFLARE.md / plan)
- Browser Run: `env.BROWSER.quickAction("markdown",{url})` works from the binding, no token, no puppeteer; returns a Response with `{success, result}` where result is the markdown string. No title field, so title = first `#` heading or the URL. No HTMLRewriter fallback needed. Env types BROWSER as Fetcher, so I cast.
- Stream: a binding exists (`"stream": {"binding":"STREAM"}`), `env.STREAM.upload(url, {creator, meta})` returns StreamVideo with `id`, `thumbnail`, `hlsPlaybackUrl`. Not in frozen Env; consumer reads it via cast and is a no-op (keeps original URL) if the binding is absent.
- Embedding: input `{text: string|string[]}`, output `{data: number[][], shape}`; 1024 dims confirmed by CLOUDFLARE.md (the doc page does not print dimensions).
- Workflows/Vectorize: as in plan; `create` on an existing id throws, so schedule falls back to `get(id)`.

## Deviations
- Vectors cap: upsert 50 items/call, topK clamped to 50. Browser URL guard also blocks single-label hosts, `.internal/.local/.lan`.
- Playback URL is stored as the HLS URL when Stream ingest completes (video may still be encoding).
- Audit row uses mode 'live' (Mode has no 'system').

## Change requests
- 02-09 (gateway.ts line 18): calls `handleBindings(req, this.env, this.ctx.props)`; must be `handleBindings(req, new URL(req.url), this.env, this.ctx.props)`.
- 02-09 (worker/index.ts line 18): queue handler type: declare `async queue(batch: MessageBatch<JobMessage>, env: Env)` in `ExportedHandler<Env>` or cast `batch as MessageBatch<JobMessage>`.
- wrangler.jsonc owner: add `"stream": {"binding":"STREAM"}`, queue producer/consumer (max_retries 5, retry_delay 60, DLQ ugecy-jobs-dlq), vectorize, d1 (migrations_dir "migrations"), kv, workflows PUBLISH_WF/ugecy-publish/PublishWorkflow, analytics dataset, browser binding; export PublishWorkflow from worker/index.ts. The config needs D1/KV id placeholders (render-config.mjs overwrites any `d1_databases[].database_id` / `kv_namespaces[].id`).
- Env owner (frozen): consider adding `STREAM?` to Env.
- Root package.json: add vitest devDependency (and a root test script).
- Orchestrator: migrations/0001_init.sql must define `audit(id,ts,thread_id,actor,agent,action,tool,status,mode,detail)` and `assets(id,url,thumbnail_url,...)`.

## Risks
- Stream upload retry may duplicate videos (AlreadyUploadedError not distinguished); `creator` is set to asset_id for traceability.
- Bootstrap parsing of `wrangler d1/vectorize list --json` and `kv namespace list` output is untested against live wrangler; queue existence is matched by grep on text output. Run once with care.
- Stream account limits read 0 in the probe; first real upload may throw QuotaReachedError and DLQ.

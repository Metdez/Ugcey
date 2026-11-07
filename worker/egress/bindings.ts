// bindings.internal: D1, Browser Run, Vectorize, media ingest, publish scheduling, metrics.
// Docs checked 2026-11-07: see .planning/phases/02-build/02-10-SUMMARY.md for differences from CLOUDFLARE.md.
import type { Env, RuntimeProps } from "../env";
import { HttpError, errorResponse, guardPublicUrl, guardSql, obj, params, str, titleFromMarkdown, truncate } from "./bindings-guards";

const EMBED_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
const MD_LIMIT = 60_000;
const BROWSER_TIMEOUT_MS = 20_000;
type Runner = (model: string, input: unknown) => Promise<{ data?: number[][] }>;
type QuickAction = { quickAction(name: string, body: unknown): Promise<Response> };

async function embed(env: Env, texts: string[]): Promise<number[][]> {
  const out = await (env.AI as unknown as { run: Runner }).run(EMBED_MODEL, { text: texts });
  if (!out.data || out.data.length !== texts.length) throw new HttpError(502, "embed_failed", "embedding returned no vectors");
  return out.data;
}

const d1Stmt = (env: Env, b: Record<string, unknown>) => env.DB.prepare(guardSql(b.sql as string)).bind(...params(b.params));

async function d1Query(env: Env, body: unknown) {
  const b = obj(body);
  str(b.sql, "sql");
  const r = await d1Stmt(env, b).all();
  return { results: r.results, meta: { changes: r.meta?.changes ?? 0, last_row_id: r.meta?.last_row_id ?? 0 } };
}

async function d1Batch(env: Env, body: unknown) {
  const list = obj(body).statements;
  if (!Array.isArray(list) || list.length === 0 || list.length > 100) throw new HttpError(400, "bad_request", "statements must be 1-100 items");
  const stmts = list.map((s) => d1Stmt(env, obj(s, "statement")));
  return { results: (await env.DB.batch(stmts)).map((r) => r.results) };
}

async function browserMarkdown(env: Env, body: unknown) {
  const url = guardPublicUrl(obj(body).url).toString();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const call = (env.BROWSER as unknown as QuickAction).quickAction("markdown", { url });
    const timeout = new Promise<never>((_, rej) => (timer = setTimeout(() => rej(new Error("timeout")), BROWSER_TIMEOUT_MS)));
    const res = await Promise.race([call, timeout]);
    const json = (await res.json()) as { success?: boolean; result?: string };
    if (!res.ok || json.success === false || typeof json.result !== "string") throw new Error(`browser run ${res.status}`);
    return { url, title: titleFromMarkdown(json.result, url), markdown: truncate(json.result, MD_LIMIT) };
  } catch (e) {
    if (e instanceof HttpError) throw e;
    throw new HttpError(502, "browser_failed", e instanceof Error ? e.message : "browser run failed");
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

async function vectorsUpsert(env: Env, body: unknown) {
  const b = obj(body);
  const namespace = str(b.namespace, "namespace", 64);
  const items = b.items;
  if (!Array.isArray(items) || items.length === 0 || items.length > 50) throw new HttpError(400, "bad_request", "items must be 1-50 entries");
  const parsed = items.map((i) => {
    const o = obj(i, "item");
    return { id: str(o.id, "id", 64), text: str(o.text, "text", 32_000), metadata: o.metadata === undefined ? {} : obj(o.metadata, "metadata") };
  });
  const values = await embed(env, parsed.map((p) => p.text));
  await env.MEMORY.upsert(
    parsed.map((p, i) => ({
      id: p.id,
      values: values[i],
      namespace,
      metadata: { ...p.metadata, text: p.text.slice(0, 1000) } as Record<string, VectorizeVectorMetadata>,
    })),
  );
  return { ok: true, count: parsed.length };
}

async function vectorsQuery(env: Env, body: unknown) {
  const b = obj(body);
  const namespace = str(b.namespace, "namespace", 64);
  const text = str(b.text, "text", 32_000);
  const topK = Math.min(50, Math.max(1, Number.isInteger(b.top_k) ? (b.top_k as number) : 5));
  const [vec] = await embed(env, [text]);
  const r = await env.MEMORY.query(vec, { topK, namespace, returnMetadata: "all" });
  return { matches: r.matches.map((m) => ({ id: m.id, score: m.score, metadata: m.metadata ?? {} })) };
}

async function mediaIngest(env: Env, body: unknown) {
  const b = obj(body);
  const asset_id = str(b.asset_id, "asset_id", 128);
  const url = guardPublicUrl(b.url).toString();
  const kind = b.kind;
  if (kind !== "image" && kind !== "video" && kind !== "audio") throw new HttpError(400, "bad_request", "kind must be image, video or audio");
  await env.JOBS.send({ kind: "media.ingest", asset_id, url, media_kind: kind });
  return { asset_id, queued: true, playback_url: url, thumbnail_url: null };
}

async function publishSchedule(env: Env, body: unknown) {
  const b = obj(body);
  const post_id = str(b.post_id, "post_id", 100);
  let publish_at: string | null = null;
  if (b.publish_at != null) {
    publish_at = str(b.publish_at, "publish_at", 40);
    if (Number.isNaN(Date.parse(publish_at))) throw new HttpError(400, "bad_request", "publish_at must be an ISO date");
  }
  try {
    const inst = await env.PUBLISH_WF.create({ id: post_id, params: { post_id, publish_at } });
    return { workflow_id: inst.id };
  } catch (e) {
    // an existing instance id means this post is already scheduled: return the same id
    try {
      return { workflow_id: (await env.PUBLISH_WF.get(post_id)).id };
    } catch {
      throw new HttpError(502, "workflow_failed", e instanceof Error ? e.message : "workflow create failed");
    }
  }
}

function metrics(env: Env, body: unknown) {
  const b = obj(body);
  const event = str(b.event, "event", 96);
  const blobs = b.blobs ?? [];
  const doubles = b.doubles ?? [];
  if (!Array.isArray(blobs) || !blobs.every((x) => typeof x === "string") || blobs.length > 19) throw new HttpError(400, "bad_request", "blobs must be up to 19 strings");
  if (!Array.isArray(doubles) || !doubles.every((x) => typeof x === "number") || doubles.length > 20) throw new HttpError(400, "bad_request", "doubles must be up to 20 numbers");
  env.METRICS.writeDataPoint({ blobs: [event, ...(blobs as string[])], doubles: doubles as number[], indexes: [event] });
  return { ok: true };
}

const ROUTES: Record<string, (env: Env, body: unknown) => unknown> = {
  "/d1/query": d1Query,
  "/d1/batch": d1Batch,
  "/browser/markdown": browserMarkdown,
  "/vectors/upsert": vectorsUpsert,
  "/vectors/query": vectorsQuery,
  "/media/ingest": mediaIngest,
  "/publish/schedule": publishSchedule,
  "/metrics": metrics,
};

export async function handleBindings(req: Request, url: URL, env: Env, _props: RuntimeProps): Promise<Response> {
  const route = ROUTES[url.pathname];
  if (!route) return errorResponse(404, "not_found", `unknown path ${url.pathname}`);
  if (req.method !== "POST") return errorResponse(405, "method_not_allowed", "POST only");
  try {
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      throw new HttpError(400, "bad_request", "body must be JSON");
    }
    return Response.json(await route(env, body));
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.status, e.code, e.message);
    return errorResponse(500, "internal", e instanceof Error ? e.message : "internal error");
  }
}

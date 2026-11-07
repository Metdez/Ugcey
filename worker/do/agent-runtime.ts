// AgentRuntime: Durable Object that owns the Python agent container (durable_object scheduling policy).
// All container-API calls live in the small helpers at the bottom so an API change stays local.
import { DurableObject } from "cloudflare:workers";
import type { Env } from "../env";
import { Glasshand } from "../glasshand/core";
import { sqlStore } from "../glasshand/store";

const PORT = 8000;
const IDLE_MS = 30 * 60_000;
const READY_TRIES = 300; // x 200 ms = 60 s; Python import is slow
const VHOSTS = [
  "llm.internal",
  "state.internal",
  "bindings.internal",
  "higgsfield.internal",
  "firecrawl.internal",
  "glasshand.internal",
];

const RUNTIME_CODE = "2026-11-07.r5";

export class AgentRuntime extends DurableObject<Env> {
  private starting?: Promise<void>;
  private gh: Glasshand;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS kv (ns TEXT NOT NULL, key TEXT NOT NULL, value BLOB, updated_at INTEGER, PRIMARY KEY (ns, key))",
    );
    this.gh = new Glasshand(sqlStore(ctx.storage));
    // The inactivity timeout is lost when the DO restarts; re-arm it for a surviving container.
    if (ctx.container?.running) void ctx.blockConcurrencyWhile(() => ctx.container!.setInactivityTimeout(IDLE_MS));
  }

  async fetch(req: Request): Promise<Response> {
    this.starting ??= this.ensureReady().finally(() => (this.starting = undefined));
    await this.starting;
    const url = new URL(req.url);
    url.protocol = "http:";
    url.host = "container";
    const fwd = new Request(url, req);
    fwd.headers.delete("host");
    return tcpPort(this.ctx).fetch(fwd); // returned unchanged so SSE streams unbuffered
  }

  // ---- operator admin RPC (routes in worker/index.ts, behind the cookie gate) ----
  async runtimeInfo(): Promise<{ code: string; running: boolean; image: string | null; info: unknown }> {
    const c = this.ctx.container!;
    const info = c.running ? await c.inspect().catch(() => null) : null;
    return { code: RUNTIME_CODE, running: c.running, image: c.images.agent ?? null, info };
  }

  /** Stop the container so the next request starts a fresh one from the currently deployed image. */
  async restartRuntime(): Promise<{ restarted: boolean }> {
    const c = this.ctx.container!;
    if (c.running) await c.destroy();
    // Reset this DO instance too, so the next request loads the newest deployed code and image map.
    this.ctx.abort("operator restart");
    return { restarted: true };
  }

  // ---- state.internal RPC (values cross RPC as base64 strings) ----
  kvGet(ns: string, prefix: string): { key: string; value_b64: string }[] {
    const rows = this.ctx.storage.sql
      .exec<{ key: string; value: ArrayBuffer }>(
        "SELECT key, value FROM kv WHERE ns = ? AND substr(key, 1, ?) = ? ORDER BY key",
        ns,
        prefix.length,
        prefix,
      )
      .toArray();
    return rows.map((r) => ({ key: r.key, value_b64: toB64(r.value) }));
  }

  kvPut(ns: string, items: { key: string; value_b64: string }[]): number {
    const now = Date.now();
    this.ctx.storage.transactionSync(() => {
      for (const it of items)
        this.ctx.storage.sql.exec(
          "INSERT INTO kv (ns, key, value, updated_at) VALUES (?, ?, ?, ?) " +
            "ON CONFLICT(ns, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
          ns,
          it.key,
          fromB64(it.value_b64),
          now,
        );
    });
    return items.length;
  }

  kvDelete(ns: string, prefix: string): number {
    return this.ctx.storage.sql.exec(
      "DELETE FROM kv WHERE ns = ? AND substr(key, 1, ?) = ?",
      ns,
      prefix.length,
      prefix,
    ).rowsWritten;
  }

  // ---- Glasshand connection (tokens live only here; see worker/glasshand/core.ts) ----
  glasshandConnect() { return this.gh.connect(); }
  glasshandStatus() { return this.gh.status(); }
  glasshandSelect(rentalId: string) { return this.gh.select(rentalId); }
  glasshandDisconnect() { return this.gh.disconnect(); }
  glasshandState() { return this.gh.state(); }
  glasshandToken(stale?: string) { return this.gh.token(stale); }

  // ---- container lifecycle ----
  private async ensureReady(): Promise<void> {
    if (!this.ctx.container?.running) await this.startContainer();
    await this.ctx.container!.setInactivityTimeout(IDLE_MS);
    const port = tcpPort(this.ctx);
    for (let i = 0; i < READY_TRIES; i++) {
      try {
        const r = await port.fetch("http://container/healthz", { signal: AbortSignal.timeout(1000) });
        await r.body?.cancel();
        if (r.ok) return;
      } catch {
        // not up yet
      }
      await scheduler.wait(200);
    }
    throw new Error("agent container not ready on :8000");
  }

  private async startContainer(): Promise<void> {
    const c = this.ctx.container!;
    const e = this.env;
    c.start({
      image: c.images.agent!,
      instance: "standard-1",
      enableInternet: false,
      env: {
        UGECY_INTERNAL_MODE: "edge",
        UGECY_WORKSPACE_ID: e.WORKSPACE_ID,
        UGECY_HAS_HIGGSFIELD: e.HF_KEY ? "true" : "false",
        UGECY_HAS_FIRECRAWL: e.FIRECRAWL_API_KEY ? "true" : "false",
        UGECY_HAS_GLASSHAND: "true", // connection is checked live via glasshand.internal/_ugecy/status,
        UGECY_DATA_DIR: "/tmp/ugecy",
      },
      labels: { app: "ugecy" },
    });
    const gw = egressGateway(this.ctx, this.ctx.id.toString());
    for (const h of VHOSTS) await c.interceptOutboundHttp(h, gw); // intercepts die with the container
    this.ctx.waitUntil(c.monitor().catch((err) => console.error("agent container exited", err)));
  }
}

// ---- container-API helpers ----
function tcpPort(ctx: DurableObjectState): Fetcher {
  return ctx.container!.getTcpPort(PORT);
}

function egressGateway(ctx: DurableObjectState, runtimeId: string): Fetcher {
  // ctx.exports is untyped without `wrangler types` GlobalProps; the loopback entrypoint exists at runtime.
  const exp = (ctx as unknown as { exports: Record<string, (o: { props: unknown }) => Fetcher> }).exports;
  return exp.EgressGateway!({ props: { runtimeId } });
}

function toB64(buf: ArrayBuffer): string {
  const b = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(s);
}

function fromB64(s: string): ArrayBuffer {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

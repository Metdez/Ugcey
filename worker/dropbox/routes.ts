// /api/dropbox/*: handled in the Worker (behind the ugecy_key gate), never proxied to the container.
import { Hono } from "hono";
import type { Env } from "../env";

export const dropbox = new Hono<{ Bindings: Env }>();

const runtime = (env: Env) => env.AGENT_RUNTIME.getByName(env.WORKSPACE_ID);
const fail = (e: unknown) =>
  Response.json({ error: { code: "upstream_error", message: e instanceof Error ? e.message : "dropbox request failed" } }, { status: 502 });

dropbox.post("/connect", async (c) => {
  try {
    const url = await runtime(c.env).dropboxConnectUrl();
    if (!url) return c.json({ error: { code: "not_configured", message: "Dropbox app keys are not set" } }, 503);
    return c.json({ authorize_url: url });
  } catch (e) {
    return fail(e);
  }
});
dropbox.post("/code", async (c) => {
  const b = (await c.req.json().catch(() => null)) as { code?: unknown } | null;
  if (typeof b?.code !== "string" || !b.code.trim()) return c.json({ error: { code: "bad_request", message: "code required" } }, 400);
  try {
    const r = await runtime(c.env).dropboxSubmitCode(b.code);
    if ("error" in r) return c.json({ error: { code: r.error, message: r.message } }, r.error === "invalid_code" ? 400 : 503);
    return c.json(r);
  } catch (e) {
    return fail(e);
  }
});
dropbox.get("/status", async (c) => runtime(c.env).dropboxStatus().then((s) => c.json(s), fail));
dropbox.post("/disconnect", async (c) => runtime(c.env).dropboxDisconnect().then((s) => c.json(s), fail));

// /api/glasshand/*: handled in the Worker (behind the ugecy_key gate), never proxied to the container.
import { Hono } from "hono";
import type { Env } from "../env";
import { streamRoute } from "./relay";

export const glasshand = new Hono<{ Bindings: Env }>();

const runtime = (env: Env) => env.AGENT_RUNTIME.getByName(env.WORKSPACE_ID);
const fail = (e: unknown) =>
  Response.json({ error: { code: "upstream_error", message: e instanceof Error ? e.message : "glasshand request failed" } }, { status: 502 });

glasshand.post("/connect", async (c) => runtime(c.env).glasshandConnect().then((s) => c.json(s), fail));
glasshand.get("/status", async (c) => runtime(c.env).glasshandStatus().then((s) => c.json(s), fail));
glasshand.post("/disconnect", async (c) => c.json(await runtime(c.env).glasshandDisconnect()));
glasshand.post("/select", async (c) => {
  const b = (await c.req.json().catch(() => null)) as { rental_id?: unknown } | null;
  if (typeof b?.rental_id !== "string" || !b.rental_id)
    return c.json({ error: { code: "bad_request", message: "rental_id required" } }, 400);
  try {
    const s = await runtime(c.env).glasshandSelect(b.rental_id);
    return c.json(s, s.state === "error" ? 404 : 200);
  } catch (e) {
    return fail(e);
  }
});
glasshand.get("/stream", (c) => streamRoute(c.req.raw, c.env, runtime(c.env)));

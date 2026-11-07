// glasshand.internal intercept: local status, allowlisted passthrough with token from the DO, one 401 refresh+retry.
import { errorResponse } from "../egress/llm";
import { glasshandAllowed } from "./allow";
import type { FetchFn, GlasshandRuntime } from "./types";

const FORWARD = ["content-type", "idempotency-key", "accept"];
const notConfigured = () => errorResponse(503, "not_configured", "Glasshand is not connected");

export async function handleGlasshand(req: Request, rt: GlasshandRuntime, f: FetchFn = (i, init) => fetch(i, init)): Promise<Response> {
  const u = new URL(req.url);
  if (u.pathname === "/_ugecy/status" && req.method === "GET") {
    const s = await rt.glasshandState();
    return Response.json({ connected: s.connected, selected_rental_id: s.selected_rental_id });
  }
  if (!glasshandAllowed(u.pathname, req.method)) return errorResponse(403, "path_not_allowed", `${req.method} ${u.pathname}`);

  let token: string | null;
  try {
    token = await rt.glasshandToken();
  } catch {
    return errorResponse(502, "upstream_error", "token refresh failed");
  }
  if (!token) return notConfigured();

  const body = req.method === "GET" ? undefined : await req.arrayBuffer(); // buffered so a 401 retry can replay it
  const send = (t: string) => {
    const headers = new Headers();
    for (const h of FORWARD) if (req.headers.has(h)) headers.set(h, req.headers.get(h)!);
    headers.set("authorization", `Bearer ${t}`);
    return f("https://api.glasshand.com" + u.pathname + u.search, { method: req.method, headers, body });
  };
  try {
    let r = await send(token);
    if (r.status === 401) {
      await r.body?.cancel();
      const fresh = await rt.glasshandToken(token);
      if (!fresh) return notConfigured();
      r = await send(fresh);
    }
    return r;
  } catch {
    return errorResponse(502, "upstream_error", "glasshand request failed");
  }
}

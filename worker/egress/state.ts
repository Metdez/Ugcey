// state.internal: namespaced KV in the AgentRuntime DO SQLite, reached via DO RPC.
import type { Env, RuntimeProps } from "../env";
import { errorResponse } from "./llm";

export async function handleState(req: Request, env: Env, props: RuntimeProps): Promise<Response> {
  if (req.method !== "POST") return errorResponse(405, "method_not_allowed", "POST only");
  const path = new URL(req.url).pathname;
  let b: { ns?: unknown; prefix?: unknown; items?: unknown };
  try {
    b = await req.json();
  } catch {
    return errorResponse(400, "bad_json", "invalid JSON body");
  }
  if (typeof b.ns !== "string" || !b.ns) return errorResponse(400, "bad_request", "ns required");
  const rt = env.AGENT_RUNTIME.get(env.AGENT_RUNTIME.idFromString(props.runtimeId));
  if (path === "/kv/get" || path === "/kv/delete") {
    if (typeof b.prefix !== "string") return errorResponse(400, "bad_request", "prefix required");
    if (path === "/kv/get") return Response.json({ items: await rt.kvGet(b.ns, b.prefix) });
    return Response.json({ ok: true, deleted: await rt.kvDelete(b.ns, b.prefix) });
  }
  if (path === "/kv/put") {
    const items = b.items;
    if (!Array.isArray(items) || items.some((i) => typeof i?.key !== "string" || typeof i?.value_b64 !== "string"))
      return errorResponse(400, "bad_request", "items [{key, value_b64}] required");
    return Response.json({ ok: true, count: await rt.kvPut(b.ns, items) });
  }
  return errorResponse(404, "not_found", path);
}

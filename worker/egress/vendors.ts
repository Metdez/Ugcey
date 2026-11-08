// higgsfield/firecrawl/tavily/glasshand/dropbox .internal: authenticated passthrough. Secrets never reach the container.
import type { Env, RuntimeProps } from "../env";
import { handleDropbox } from "../dropbox/egress";
import { glasshandAllowed } from "../glasshand/allow";
import { handleGlasshand } from "../glasshand/egress";
import { errorResponse } from "./llm";

interface Vendor {
  base: string;
  auth: (env: Env) => string | undefined;
  allowed: (path: string, method?: string) => boolean;
}

const under = (path: string, prefix: string) => path === prefix || path.startsWith(prefix + "/");

export const VENDORS: Record<string, Vendor> = {
  "higgsfield.internal": {
    base: "https://api.higgsfield.ai",
    auth: (e) => (e.HF_KEY ? `Key ${e.HF_KEY}` : undefined),
    allowed: (p) => !under(p, "/v1/agent"),
  },
  "firecrawl.internal": {
    base: "https://api.firecrawl.dev",
    auth: (e) => (e.FIRECRAWL_API_KEY ? `Bearer ${e.FIRECRAWL_API_KEY}` : undefined),
    allowed: (p) => under(p, "/v2/search") || under(p, "/v2/scrape"),
  },
  "tavily.internal": { // no /crawl or /map: platform pages can't be crawled (source policy)
    base: "https://api.tavily.com",
    auth: (e) => (e.TAVILY_API_KEY ? `Bearer ${e.TAVILY_API_KEY}` : undefined),
    allowed: (p, m) => (m === "POST" && /^\/(search|extract|research)$/.test(p)) || (m === "GET" && /^\/research\/[\w-]+$/.test(p)),
  },
  "glasshand.internal": {
    base: "https://api.glasshand.com",
    auth: () => undefined, // token comes from the AgentRuntime DO, see handleGlasshand
    allowed: glasshandAllowed,
  },
};

export async function handleVendor(req: Request, env: Env, props: RuntimeProps): Promise<Response> {
  const u = new URL(req.url);
  if (u.hostname === "glasshand.internal")
    return handleGlasshand(req, env.AGENT_RUNTIME.get(env.AGENT_RUNTIME.idFromString(props.runtimeId)));
  if (u.hostname === "dropbox.internal")
    return handleDropbox(req, env.AGENT_RUNTIME.get(env.AGENT_RUNTIME.idFromString(props.runtimeId)));
  const v = VENDORS[u.hostname];
  if (!v) return errorResponse(403, "egress_denied", u.hostname);
  if (!v.allowed(u.pathname, req.method)) return errorResponse(403, "path_not_allowed", `${req.method} ${u.pathname}`);
  const auth = v.auth(env);
  if (!auth) return errorResponse(503, "not_configured", `${u.hostname} has no credential`);
  const headers = new Headers(req.headers);
  headers.delete("authorization");
  headers.delete("host");
  headers.set("authorization", auth);
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  try { // upstream status, headers (Retry-After) and body pass through unchanged
    return await fetch(v.base + u.pathname + u.search, { method: req.method, headers, body: hasBody ? req.body : undefined });
  } catch (e) {
    return errorResponse(502, "upstream_error", e instanceof Error ? e.message : String(e));
  }
}

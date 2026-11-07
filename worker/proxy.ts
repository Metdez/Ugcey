// Forward a request to the workspace AgentRuntime DO; response returned unmodified (SSE streams through).
import type { Env } from "./env";

export function proxyToRuntime(req: Request, env: Env): Promise<Response> {
  return env.AGENT_RUNTIME.getByName(env.WORKSPACE_ID).fetch(req);
}

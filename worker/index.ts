import { Hono } from "hono";
import { requireKey, unlock } from "./auth";
import { dropbox } from "./dropbox/routes";
import { glasshand } from "./glasshand/routes";
import type { Env, JobMessage } from "./env";
import { proxyToRuntime } from "./proxy";
import { handleQueue } from "./queues/consumer";

const app = new Hono<{ Bindings: Env }>();

app.get("/api/edge/health", (c) => c.json({ ok: true, edge: true }));
app.get("/api/edge/unlock", (c) => unlock(c));
app.use("/api/*", requireKey);
app.route("/api/glasshand", glasshand); // before the container proxy, after the cookie gate
app.route("/api/dropbox", dropbox);
const runtime = (env: Env) => env.AGENT_RUNTIME.get(env.AGENT_RUNTIME.idFromName(env.WORKSPACE_ID));
app.get("/api/runtime/info", async (c) => c.json(await runtime(c.env).runtimeInfo()));
app.post("/api/runtime/restart", async (c) => {
  try {
    return c.json(await runtime(c.env).restartRuntime());
  } catch {
    return c.json({ restarted: true, reset: true }); // ctx.abort() surfaces as an error to the caller
  }
});
app.all("/api/*", (c) => proxyToRuntime(c.req.raw, c.env));

export { AgentRuntime } from "./do/agent-runtime";
export { EgressGateway } from "./egress/gateway";
export { PublishWorkflow } from "./workflows/publish";

export default {
  fetch: app.fetch,
  queue: (batch, env) => handleQueue(batch as MessageBatch<JobMessage>, env),
} satisfies ExportedHandler<Env>;

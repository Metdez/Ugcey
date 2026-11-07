// STUB (owned by plan 02-09): Durable Object that owns the agent container.
import { DurableObject } from "cloudflare:workers";
import type { Env } from "../env";

export class AgentRuntime extends DurableObject<Env> {
  async fetch(_req: Request): Promise<Response> {
    return new Response("agent runtime not implemented", { status: 501 });
  }
}

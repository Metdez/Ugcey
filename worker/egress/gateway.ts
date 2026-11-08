// EgressGateway: handles every intercepted *.internal request from the container. Holds all secrets/bindings.
import { WorkerEntrypoint } from "cloudflare:workers";
import type { Env, RuntimeProps } from "../env";
import { handleBindings } from "./bindings";
import { errorResponse, handleLlm } from "./llm";
import { handleState } from "./state";
import { handleUploadRelay } from "./upload-relay";
import { handleVendor } from "./vendors";

export class EgressGateway extends WorkerEntrypoint<Env, RuntimeProps> {
  async fetch(req: Request): Promise<Response> {
    const host = new URL(req.url).hostname;
    switch (host) {
      case "llm.internal":
        return handleLlm(req, this.env);
      case "state.internal":
        return handleState(req, this.env, this.ctx.props);
      case "bindings.internal":
        return handleBindings(req, new URL(req.url), this.env, this.ctx.props);
      case "hfupload.internal":
        return handleUploadRelay(req);
      case "higgsfield.internal":
      case "firecrawl.internal":
      case "tavily.internal":
      case "glasshand.internal":
      case "dropbox.internal":
        return handleVendor(req, this.env, this.ctx.props);
      default:
        this.env.METRICS.writeDataPoint({ blobs: ["egress_denied", host], doubles: [1], indexes: ["egress"] });
        return errorResponse(403, "egress_denied", host);
    }
  }
}

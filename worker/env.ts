// Worker bindings. Frozen contract shared by worker/** modules; names match wrangler.jsonc.
import type { AgentRuntime } from "./do/agent-runtime";

export interface Env {
  ASSETS: Fetcher;
  AI: Ai; // Workers AI (Chinese models via OpenAI-schema run())
  DB: D1Database; // ugecy-db (migrations/)
  KV: KVNamespace; // ugecy-cache
  MEMORY: VectorizeIndex; // ugecy-memory (1024-d cosine, qwen3-embedding-0.6b)
  JOBS: Queue<JobMessage>; // ugecy-jobs (+ ugecy-jobs-dlq)
  PUBLISH_WF: Workflow<PublishParams>; // ugecy-publish
  BROWSER: Fetcher; // Browser Run
  METRICS: AnalyticsEngineDataset; // ugecy_events
  AGENT_RUNTIME: DurableObjectNamespace<AgentRuntime>;

  // vars
  WORKSPACE_ID: string; // "default"
  AI_GATEWAY_ID?: string; // optional AI Gateway id for env.AI.run(..., { gateway })

  // secrets (wrangler secret put). Optional ones switch providers to mock mode when absent.
  UGECY_ACCESS_KEY: string; // operator access key (cookie gate)
  HF_KEY?: string; // Higgsfield "key-id:key-secret"
  FIRECRAWL_API_KEY?: string;
  GLASSHAND_TOKEN?: string;
}

export interface PublishParams {
  post_id: string;
  publish_at?: string | null; // ISO; absent = now
}

export type JobMessage =
  | { kind: "media.ingest"; asset_id: string; url: string; media_kind: "image" | "video" | "audio" }
  | { kind: "metric"; event: string; blobs: string[]; doubles: number[] };

export interface RuntimeProps {
  runtimeId: string;
}

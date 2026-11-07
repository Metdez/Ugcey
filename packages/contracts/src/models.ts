// Shared domain models. Source of truth for the UI; mirrored 1:1 in
// services/agent/ugecy/contracts.py (pydantic). Change both together.

export type Mode = "live" | "mock";
export type ISODate = string;

/** Provider modes reported by the backend so the UI can show mock badges. */
export interface ProviderModes {
  llm: Mode;
  media: Mode;
  device: Mode;
  publishing: Mode;
  research: Mode;
}

export interface ModelRoute {
  role: string; // "orchestrator" | "research" | "creative" | "critic" | "fast" | "vision" | "embeddings"
  model: string; // e.g. "@cf/zai-org/glm-5.3"
  fallback?: string | null;
}

export interface AgentInfo {
  name: string; // "orchestrator", "research-analyst", ...
  description: string;
  model: string;
  tools: string[];
  enabled: boolean;
}

export interface AppConfig {
  version: string;
  modes: ProviderModes;
  models: ModelRoute[];
  agents: AgentInfo[];
  starter_prompts: string[];
}

export type TodoStatus = "pending" | "in_progress" | "completed";
export interface Todo {
  content: string;
  status: TodoStatus;
}

/** A file in the agent's virtual filesystem (thread-scoped StateBackend). */
export interface FileEntry {
  path: string; // "/research/skincare-hooks.md"
  size: number; // bytes of content
  modified_at: ISODate | null;
}

export interface FileContent {
  path: string;
  content: string;
}

/** Long-term memory / skills (cross-thread Store). */
export interface MemoryFile {
  path: string; // "/memories/AGENTS.md" or "/skills/ugc-hook-extraction/SKILL.md"
  scope: "memories" | "skills";
  content: string;
  updated_at: ISODate | null;
  editable: boolean; // skills are read-only for the agent and the UI
}

export type Role = "user" | "assistant" | "tool";
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

/** History replay item (GET /api/threads/:id). Streaming uses events instead. */
export interface ChatMessage {
  id: string;
  role: Role;
  agent: string; // "orchestrator" or subagent name; "operator" for user
  text: string;
  reasoning?: string | null;
  tool_calls?: ToolCall[];
  tool_call_id?: string | null; // for role=tool
  name?: string | null; // tool name for role=tool
  created_at?: ISODate | null;
}

export type DecisionType = "approve" | "edit" | "reject";

/** One gated tool call inside an approval interrupt. */
export interface ApprovalRequest {
  tool: string;
  agent: string;
  args: Record<string, unknown>;
  description: string;
  allowed_decisions: DecisionType[];
  estimated_cost_usd?: number | null;
}

export interface ApprovalRecord {
  interrupt_id: string;
  thread_id: string;
  status: "pending" | "approved" | "edited" | "rejected" | "expired";
  requests: ApprovalRequest[];
  created_at: ISODate;
  decided_at?: ISODate | null;
}

export type Decision =
  | { type: "approve" }
  | { type: "edit"; args: Record<string, unknown> }
  | { type: "reject"; message?: string };

export type AssetKind = "image" | "video" | "audio";
export type AssetStatus = "queued" | "in_progress" | "completed" | "failed";
export interface Asset {
  id: string;
  thread_id: string | null;
  kind: AssetKind;
  status: AssetStatus;
  provider: string; // "higgsfield" | "mock"
  model: string; // endpoint id, e.g. "higgsfield-ai/soul/v2/standard"
  prompt: string;
  url: string | null;
  thumbnail_url: string | null;
  job_id: string | null;
  mode: Mode;
  estimated_usd: number | null;
  created_at: ISODate;
}

/** A research source the agent looked at (public, permitted). */
export interface Source {
  url: string;
  title: string;
  platform: string | null; // "tiktok" | "youtube" | "instagram" | "web"
  snippet: string | null;
}

export type Platform = "tiktok" | "instagram" | "youtube" | "facebook";
export interface ConnectedAccount {
  id: string;
  platform: Platform;
  handle: string;
  mode: Mode;
  status: "connected" | "needs_auth" | "error";
}

export interface Post {
  id: string;
  thread_id: string | null;
  account_id: string;
  asset_id: string | null;
  caption: string;
  ai_disclosure: boolean;
  status: "draft" | "scheduled" | "published" | "failed";
  publish_at: ISODate | null;
  external_url: string | null;
  mode: Mode;
  created_at: ISODate;
}

export interface AuditEntry {
  id: string;
  ts: ISODate;
  thread_id: string | null;
  actor: "agent" | "operator" | "system";
  agent: string | null;
  action: string; // "tool_call" | "approval" | "publish" | "media_job" | ...
  tool: string | null;
  status: "ok" | "error" | "pending" | "rejected";
  mode: Mode;
  detail: string;
}

export interface ThreadSummary {
  id: string;
  title: string;
  created_at: ISODate;
  updated_at: ISODate;
  status: "idle" | "running" | "awaiting_approval" | "error";
}

export interface ThreadState {
  thread: ThreadSummary;
  messages: ChatMessage[];
  todos: Todo[];
  files: FileEntry[];
  sources: Source[];
  pending_approval: ApprovalRecord | null;
}

export interface DeviceInfo {
  id: string;
  name: string;
  kind: "iphone" | "mac";
  status: string;
  ready: boolean;
}

export interface DeviceStatus {
  provider: string; // "glasshand" | "mock"
  mode: Mode;
  devices: DeviceInfo[];
  session: { id: string; device_id: string; goal: string; steps_used: number; max_steps: number } | null;
  control: "agent" | "human" | "idle";
  last_action: string | null;
}

// UI-side view model. Built from wire events (@ugecy/contracts) by stores/apply-event.ts.
// Frozen seam between WP-A (shell/stores), WP-B (chat) and WP-C (inspector).
import type {
  ApprovalRecord, Asset, Decision, FileEntry, Source, Todo,
} from "@ugecy/contracts";

export type * from "@ugecy/contracts";

export type InspectorTab =
  | "plan" | "agents" | "files" | "memory" | "sources" | "assets" | "approvals" | "audit" | "device";

export type RunStatus = "idle" | "connecting" | "streaming" | "interrupted" | "error" | "offline";

export interface ToolCallView {
  id: string;
  name: string;
  args: Record<string, unknown>;
  agent: string; // orchestrator or subagent name
  parentCallId: string | null; // `task` call id when made inside a subagent
  status: "running" | "complete" | "error" | "awaiting_approval";
  output?: string;
  startedAt: string;
  endedAt?: string;
}

export interface SubagentRunView {
  id: string; // the parent's `task` tool_call id
  name: string; // "research-analyst"
  task: string; // description passed to the subagent
  status: "running" | "complete" | "error";
  model?: string;
  toolCallIds: string[];
  text: string; // streamed subagent narration
  result?: string; // summary returned to the orchestrator
  startedAt: string;
  endedAt?: string;
  parentMessageId: string;
}

export type MessagePart =
  | { type: "text"; text: string }
  | { type: "reasoning"; text: string }
  | { type: "tool"; toolCallId: string }
  | { type: "subagent"; subagentId: string }
  | { type: "approval"; approvalId: string } // = interrupt_id
  | { type: "assets"; assetIds: string[] }
  | { type: "plan" }
  | { type: "error"; message: string; retryable: boolean };

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  agent: string;
  createdAt: string;
  parts: MessagePart[];
  status: "streaming" | "complete" | "error" | "interrupted";
  model?: string;
}

export interface ThreadSnapshot {
  threadId: string | null;
  title: string;
  status: RunStatus;
  runId: string | null;
  lastSeq: number;
  messages: UiMessage[];
  todos: Todo[];
  toolCalls: Record<string, ToolCallView>;
  subagents: Record<string, SubagentRunView>;
  files: FileEntry[];
  sources: Source[];
  assets: Record<string, Asset>;
  approvals: Record<string, ApprovalRecord>; // keyed by interrupt_id
  progress: string | null; // latest progress line
  error: { message: string; retryable: boolean } | null;
}

export interface ThreadActions {
  openThread(id: string | null): Promise<void>; // null = new empty chat
  send(text: string): Promise<void>; // creates the thread if needed
  ensureThread(title: string): Promise<string>; // current thread id, creating the thread first if there is none
  stop(): Promise<void>;
  decide(interruptId: string, decisions: Decision[]): Promise<void>;
  refreshAssets(): Promise<void>;
}

export const emptySnapshot = (): ThreadSnapshot => ({
  threadId: null, title: "New chat", status: "idle", runId: null, lastSeq: 0,
  messages: [], todos: [], toolCalls: {}, subagents: {}, files: [], sources: [],
  assets: {}, approvals: {}, progress: null, error: null,
});

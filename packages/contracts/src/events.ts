// Server-sent events streamed by POST /api/threads/:id/runs and /resume.
// Wire format (SSE): `event: <type>\ndata: <json UiEvent>\n\n`, keepalive `: ping` comments.
// Produced by services/agent/ugecy/stream/ from LangGraph astream(version="v2", subgraphs=True).
import type { ApprovalRequest, Asset, FileEntry, Source, Todo } from "./models";

export interface EventBase {
  seq: number; // monotonically increasing per run
  ts: string; // ISO time
  thread_id: string;
  run_id: string;
  /** Agent that produced the event: "orchestrator" or a subagent name (metadata lc_agent_name). */
  agent: string;
  /** LangGraph namespace: [] for the orchestrator, ["tools:<task_call_id>"] for a subagent. */
  ns: string[];
  /** For subagent events: the parent `task` tool_call id (metadata lc_subagent_tool_call_id). */
  parent_call_id: string | null;
}

export type UiEvent =
  | (EventBase & { type: "run.started"; model: string | null })
  /** Streamed assistant text. Concatenate `text` by message_id. */
  | (EventBase & { type: "message.delta"; message_id: string; text: string })
  /** Streamed model reasoning ("thinking"); render collapsed. */
  | (EventBase & { type: "reasoning.delta"; message_id: string; text: string })
  | (EventBase & { type: "message.completed"; message_id: string; text: string })
  /** A tool call the model made (args complete). `task` calls also emit subagent.started. */
  | (EventBase & { type: "tool.started"; call_id: string; name: string; args: Record<string, unknown> })
  | (EventBase & {
      type: "tool.completed";
      call_id: string;
      name: string;
      status: "ok" | "error";
      output_preview: string; // ≤ 2000 chars
    })
  | (EventBase & { type: "subagent.started"; call_id: string; subagent: string; description: string })
  | (EventBase & { type: "subagent.completed"; call_id: string; subagent: string; status: "ok" | "error"; summary: string })
  /** Full replacement of the orchestrator's todo list. */
  | (EventBase & { type: "todos.updated"; todos: Todo[] })
  /** Full replacement of the thread's virtual file index (no contents; fetch via REST). */
  | (EventBase & { type: "files.updated"; files: FileEntry[] })
  | (EventBase & { type: "source.added"; source: Source })
  | (EventBase & { type: "asset.updated"; asset: Asset })
  | (EventBase & { type: "memory.updated"; path: string })
  /** Free-form progress from tools (get_stream_writer). */
  | (EventBase & { type: "progress"; tool: string | null; message: string })
  /** Run paused for human approval. Resume with POST /api/threads/:id/resume. */
  | (EventBase & { type: "approval.requested"; interrupt_id: string; requests: ApprovalRequest[] })
  | (EventBase & { type: "run.completed"; status: "done" | "interrupted" | "error" | "cancelled" })
  | (EventBase & { type: "error"; message: string; retryable: boolean });

export type UiEventType = UiEvent["type"];

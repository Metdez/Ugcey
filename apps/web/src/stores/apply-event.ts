// Pure reducer: wire UiEvent -> UI view model. No I/O. See types/agent.ts for the model.
import type {
  MessagePart, SubagentRunView, ThreadSnapshot, ToolCallView, UiEvent, UiMessage,
} from "@/types/agent";

const isSub = (e: UiEvent) => !!e.parent_call_id && e.agent !== "orchestrator";

const last = <T,>(a: T[]) => a[a.length - 1];

/** Replace one message by id (immutably). */
const patchMsg = (s: ThreadSnapshot, id: string, f: (m: UiMessage) => UiMessage): ThreadSnapshot => ({
  ...s, messages: s.messages.map((m) => (m.id === id ? f(m) : m)),
});

/** Find (or create) the assistant message an event belongs to. */
function ensureMsg(s: ThreadSnapshot, e: UiEvent, id?: string): [ThreadSnapshot, string] {
  if (id) {
    if (s.messages.some((m) => m.id === id)) return [s, id];
  } else {
    const l = last(s.messages);
    if (l && l.role === "assistant") return [s, l.id];
    id = `run-${e.run_id}`;
  }
  const m: UiMessage = { id, role: "assistant", agent: e.agent, createdAt: e.ts, parts: [], status: "streaming" };
  return [{ ...s, messages: [...s.messages, m] }, id];
}

const addPart = (s: ThreadSnapshot, id: string, p: MessagePart) =>
  patchMsg(s, id, (m) => ({ ...m, parts: [...m.parts, p] }));

function appendText(s: ThreadSnapshot, id: string, type: "text" | "reasoning", text: string) {
  return patchMsg(s, id, (m) => {
    const l = last(m.parts);
    if (l && l.type === type) return { ...m, parts: [...m.parts.slice(0, -1), { type, text: l.text + text }] };
    return { ...m, parts: [...m.parts, { type, text }] };
  });
}

function ensureSub(s: ThreadSnapshot, e: UiEvent, id: string, patch: Partial<SubagentRunView>): [ThreadSnapshot, boolean] {
  const prev = s.subagents[id];
  const sub: SubagentRunView = {
    id, name: e.agent, task: "", status: "running", toolCallIds: [], text: "", startedAt: e.ts,
    parentMessageId: "", ...prev, ...patch,
  };
  return [{ ...s, subagents: { ...s.subagents, [id]: sub } }, !prev];
}

/** Subagent (`task` call) bookkeeping: view entry + one message part. */
function upsertSubagent(s: ThreadSnapshot, e: UiEvent, id: string, patch: Partial<SubagentRunView>) {
  let msgId: string;
  [s, msgId] = ensureMsg(s, e);
  const [s2, created] = ensureSub(s, e, id, { parentMessageId: s.subagents[id]?.parentMessageId || msgId, ...patch });
  return created ? addPart(s2, msgId, { type: "subagent", subagentId: id }) : s2;
}

const argStr = (a: Record<string, unknown>, k: string) => (typeof a[k] === "string" ? (a[k] as string) : "");

const MESSAGE_DONE: Record<string, UiMessage["status"]> = {
  done: "complete", cancelled: "complete", error: "error", interrupted: "interrupted",
};

export function applyEvent(s: ThreadSnapshot, e: UiEvent): ThreadSnapshot {
  if (e.run_id === s.runId && e.seq <= s.lastSeq) return s; // duplicate / replayed
  if (e.run_id !== s.runId) s = { ...s, runId: e.run_id, lastSeq: 0 };
  s = { ...s, lastSeq: e.seq };
  let id: string;

  switch (e.type) {
    case "run.started":
      return { ...s, status: "streaming", error: null, progress: null };

    case "message.delta":
    case "reasoning.delta": {
      if (isSub(e)) {
        if (e.type === "reasoning.delta") return s;
        const pid = e.parent_call_id!;
        const [s2] = ensureSub(s, e, pid, {});
        const sub = s2.subagents[pid];
        return { ...s2, subagents: { ...s2.subagents, [pid]: { ...sub, text: sub.text + e.text } } };
      }
      [s, id] = ensureMsg(s, e, e.message_id);
      return appendText(s, id, e.type === "message.delta" ? "text" : "reasoning", e.text);
    }

    case "message.completed": {
      if (isSub(e)) return s;
      [s, id] = ensureMsg(s, e, e.message_id);
      return patchMsg(s, id, (m) => ({
        ...m, status: m.status === "streaming" ? "complete" : m.status,
        parts: m.parts.some((p) => p.type === "text") || !e.text ? m.parts : [...m.parts, { type: "text", text: e.text }],
      }));
    }

    case "tool.started": {
      if (e.name === "task") {
        const a = e.args;
        return upsertSubagent(s, e, e.call_id, {
          name: argStr(a, "subagent_type") || argStr(a, "subagent") || "subagent", task: argStr(a, "description"),
        });
      }
      const call: ToolCallView = {
        id: e.call_id, name: e.name, args: e.args, agent: e.agent, parentCallId: e.parent_call_id,
        status: "running", startedAt: e.ts,
      };
      if (s.toolCalls[e.call_id]) return s;
      s = { ...s, toolCalls: { ...s.toolCalls, [e.call_id]: call } };
      if (isSub(e)) {
        const [s2] = ensureSub(s, e, e.parent_call_id!, {});
        const sub = s2.subagents[e.parent_call_id!];
        return { ...s2, subagents: { ...s2.subagents, [sub.id]: { ...sub, toolCallIds: [...sub.toolCallIds, e.call_id] } } };
      }
      [s, id] = ensureMsg(s, e);
      return addPart(s, id, { type: "tool", toolCallId: e.call_id });
    }

    case "tool.completed": {
      const ok = e.status === "ok";
      if (e.name === "task") {
        return upsertSubagent(s, e, e.call_id, {
          status: ok ? "complete" : "error", result: e.output_preview, endedAt: e.ts,
        });
      }
      const prev = s.toolCalls[e.call_id];
      if (!prev) return s;
      const call: ToolCallView = {
        ...prev, status: ok ? "complete" : "error", output: e.output_preview, endedAt: e.ts,
      };
      return { ...s, toolCalls: { ...s.toolCalls, [e.call_id]: call } };
    }

    case "subagent.started":
      return upsertSubagent(s, e, e.call_id, { name: e.subagent, task: e.description });

    case "subagent.completed":
      return upsertSubagent(s, e, e.call_id, {
        name: e.subagent, status: e.status === "ok" ? "complete" : "error", result: e.summary, endedAt: e.ts,
      });

    case "todos.updated": return { ...s, todos: e.todos };
    case "files.updated": return { ...s, files: e.files };
    case "source.added":
      return s.sources.some((x) => x.url === e.source.url) ? s : { ...s, sources: [...s.sources, e.source] };

    case "asset.updated": {
      const had = !!s.assets[e.asset.id];
      s = { ...s, assets: { ...s.assets, [e.asset.id]: e.asset } };
      if (had) return s;
      [s, id] = ensureMsg(s, e);
      return patchMsg(s, id, (m) => {
        const i = m.parts.findIndex((p) => p.type === "assets");
        const p = m.parts[i];
        if (p?.type !== "assets") return { ...m, parts: [...m.parts, { type: "assets", assetIds: [e.asset.id] }] };
        const parts = m.parts.slice();
        parts[i] = { type: "assets", assetIds: [...p.assetIds, e.asset.id] };
        return { ...m, parts };
      });
    }

    case "approval.requested": {
      if (s.approvals[e.interrupt_id]) return { ...s, status: "interrupted" };
      const tools = new Set(e.requests.map((r) => r.tool));
      const toolCalls = { ...s.toolCalls };
      for (const c of Object.values(toolCalls)) {
        if (c.status === "running" && tools.has(c.name)) toolCalls[c.id] = { ...c, status: "awaiting_approval" };
      }
      s = {
        ...s, toolCalls, status: "interrupted",
        approvals: { ...s.approvals, [e.interrupt_id]: {
          interrupt_id: e.interrupt_id, thread_id: e.thread_id, status: "pending", requests: e.requests, created_at: e.ts,
        } },
      };
      [s, id] = ensureMsg(s, e);
      return addPart(s, id, { type: "approval", approvalId: e.interrupt_id });
    }

    case "progress": return { ...s, progress: e.message };

    case "run.completed": {
      const done = MESSAGE_DONE[e.status];
      const status = e.status === "error" ? "error" : e.status === "interrupted" ? "interrupted" : "idle";
      return {
        ...s, status, progress: null,
        messages: s.messages.map((m) => (m.status === "streaming" ? { ...m, status: done } : m)),
      };
    }

    case "error": {
      [s, id] = ensureMsg(s, e);
      s = { ...s, status: "error", error: { message: e.message, retryable: e.retryable } };
      return addPart(s, id, { type: "error", message: e.message, retryable: e.retryable });
    }

    default: return s; // memory.updated etc.: inspector refetches on demand
  }
}

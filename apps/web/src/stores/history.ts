// ChatMessage[] (GET /api/threads/:id) -> UI view model.
import type { ChatMessage, MessagePart, SubagentRunView, ThreadSnapshot, ToolCallView, UiMessage } from "@/types/agent";

type Slice = Pick<ThreadSnapshot, "messages" | "toolCalls" | "subagents">;

export function historyToUi(history: ChatMessage[]): Slice {
  const messages: UiMessage[] = [];
  const toolCalls: Record<string, ToolCallView> = {};
  const subagents: Record<string, SubagentRunView> = {};
  const now = new Date().toISOString();

  for (const h of history) {
    const at = h.created_at ?? now;
    if (h.role === "user") {
      messages.push({ id: h.id, role: "user", agent: "operator", createdAt: at, parts: [{ type: "text", text: h.text }], status: "complete" });
    } else if (h.role === "assistant") {
      if (h.agent !== "orchestrator") continue; // shortcut: subagent-internal turns have no parent id in history
      const parts: MessagePart[] = [];
      if (h.reasoning) parts.push({ type: "reasoning", text: h.reasoning });
      if (h.text) parts.push({ type: "text", text: h.text });
      for (const c of h.tool_calls ?? []) {
        if (c.name === "task") {
          const a = c.args;
          subagents[c.id] = {
            id: c.id, name: String(a.subagent_type ?? "subagent"), task: String(a.description ?? ""),
            status: "running", toolCallIds: [], text: "", startedAt: at, parentMessageId: h.id,
          };
          parts.push({ type: "subagent", subagentId: c.id });
        } else {
          toolCalls[c.id] = { id: c.id, name: c.name, args: c.args, agent: h.agent, parentCallId: null, status: "running", startedAt: at };
          parts.push({ type: "tool", toolCallId: c.id });
        }
      }
      messages.push({ id: h.id, role: "assistant", agent: h.agent, createdAt: at, parts, status: "complete" });
    } else if (h.tool_call_id) {
      const id = h.tool_call_id;
      if (subagents[id]) subagents[id] = { ...subagents[id], status: "complete", result: h.text, endedAt: at };
      else if (toolCalls[id]) toolCalls[id] = { ...toolCalls[id], status: "complete", output: h.text, endedAt: at };
    }
  }
  return { messages, toolCalls, subagents };
}

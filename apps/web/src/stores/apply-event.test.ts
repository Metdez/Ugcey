import { describe, expect, it } from "vitest";
import type { UiEvent } from "@ugecy/contracts";
import { emptySnapshot } from "@/types/agent";
import { applyEvent } from "./apply-event";
import { mockResume, mockRun } from "@/fixtures/mock-run";

let seq = 0;
const ev = (type: string, body: object, parent: string | null = null, agent = "orchestrator", run = "r1"): UiEvent =>
  ({ seq: ++seq, ts: "2026-01-01T00:00:00Z", thread_id: "t", run_id: run, agent, ns: [], parent_call_id: parent, type, ...body }) as UiEvent;
const fold = (events: UiEvent[]) => events.reduce(applyEvent, emptySnapshot());

describe("applyEvent", () => {
  it("nests subagent tools and text under the task, not the message", () => {
    seq = 0;
    const s = fold([
      ev("message.delta", { message_id: "m", text: "Hel" }),
      ev("message.delta", { message_id: "m", text: "lo" }),
      ev("tool.started", { call_id: "c1", name: "task", args: { subagent_type: "research-analyst", description: "d" } }),
      ev("message.delta", { message_id: "x", text: "narr" }, "c1", "research-analyst"),
      ev("tool.started", { call_id: "w1", name: "web_search", args: {} }, "c1", "research-analyst"),
      ev("tool.completed", { call_id: "w1", name: "web_search", status: "error", output_preview: "boom" }, "c1", "research-analyst"),
      ev("tool.completed", { call_id: "c1", name: "task", status: "ok", output_preview: "done" }),
    ]);
    expect(s.messages).toHaveLength(1);
    expect(s.messages[0].parts).toEqual([{ type: "text", text: "Hello" }, { type: "subagent", subagentId: "c1" }]);
    expect(s.subagents.c1).toMatchObject({ name: "research-analyst", text: "narr", toolCallIds: ["w1"], status: "complete", result: "done" });
    expect(s.toolCalls.w1).toMatchObject({ status: "error", output: "boom", parentCallId: "c1" });
  });

  it("adds approvals, interrupts, and completes", () => {
    seq = 0;
    const s = fold([
      ev("tool.started", { call_id: "g", name: "generate_media", args: {} }),
      ev("approval.requested", { interrupt_id: "i1", requests: [{ tool: "generate_media", agent: "a", args: {}, description: "", allowed_decisions: ["approve"] }] }),
    ]);
    expect(s.status).toBe("interrupted");
    expect(s.approvals.i1.status).toBe("pending");
    expect(s.toolCalls.g.status).toBe("awaiting_approval");
    expect(s.messages[0].parts.at(-1)).toEqual({ type: "approval", approvalId: "i1" });
    expect(applyEvent(s, ev("run.completed", { status: "interrupted" })).messages[0].status).toBe("interrupted");
  });

  it("dedupes sources and ignores replayed seq", () => {
    seq = 0;
    const src = { url: "https://a", title: "A", platform: null, snippet: null };
    const a = ev("source.added", { source: src });
    let s = fold([a, ev("source.added", { source: src })]);
    expect(s.sources).toHaveLength(1);
    const before = s;
    s = applyEvent(s, a); // seq 1 <= lastSeq 2
    expect(s).toBe(before);
    s = applyEvent(s, ev("progress", { tool: null, message: "x" }, null, "orchestrator", "r2")); // new run resets seq
    expect(s.progress).toBe("x");
  });

  it("replays the full mock timeline without orphaning tool calls", () => {
    const s1 = fold(mockRun("t", "hi").map((e) => ({ ...e, thread_id: "t" })));
    expect(s1.status).toBe("interrupted");
    expect(Object.keys(s1.subagents).sort()).toEqual(["call-c1", "call-r1"]);
    expect(s1.subagents["call-r1"].toolCallIds).toHaveLength(4);
    const s2 = mockResume("t", [{ type: "approve" }]).reduce(applyEvent, s1);
    expect(s2.status).toBe("idle");
    expect(s2.assets["asset-1"].status).toBe("completed");
  });
});

import { emptySnapshot, type ThreadSnapshot } from "@/types/agent";

const t = "2026-11-07T14:00:00Z";
const ap = (id: string, tool: string, args: Record<string, unknown>, cost?: number) => ({
  interrupt_id: id, thread_id: "t1", status: "pending" as const, created_at: t,
  requests: [{ tool, agent: "publishing", args, description: tool === "publish_post" ? "Publish 1 video to @glowco on TikTok?" : "Generate 3 videos?",
    allowed_decisions: ["approve", "edit", "reject"] as const, estimated_cost_usd: cost }].map((r) => ({ ...r, allowed_decisions: [...r.allowed_decisions] })),
});
const asset = (id: string, status: "completed" | "in_progress" | "failed", mode: "live" | "mock" = "mock") => ({
  id, thread_id: "t1", kind: "video" as const, status, provider: mode === "mock" ? "mock" : "higgsfield",
  model: "higgsfield-ai/soul/v2/standard", prompt: "Creator unboxing a serum, handheld, warm light", url: null, thumbnail_url: null,
  job_id: null, mode, estimated_usd: 0.4, created_at: t,
});

export const fixtureSnapshot: ThreadSnapshot = {
  ...emptySnapshot(), threadId: "t1", title: "Skincare hooks", status: "interrupted", progress: "Step 3/7 — Writing hook variants",
  messages: [
    { id: "u1", role: "user", agent: "user", createdAt: t, status: "complete", parts: [{ type: "text", text: "Find the top UGC hooks for clean skincare and make 3 videos." }] },
    { id: "a1", role: "assistant", agent: "orchestrator", createdAt: t, status: "interrupted", model: "kimi-k2", parts: [
      { type: "reasoning", text: "Plan: research, script, generate, publish." },
      { type: "plan" },
      { type: "tool", toolCallId: "c1" },
      { type: "subagent", subagentId: "s1" },
      { type: "text", text: "Found **3 patterns**:\n\n1. Problem-first hook\n2. Ingredient reveal\n3. Before/after\n\n| Hook | Views |\n|---|---|\n| A | 1.2M |" },
      { type: "tool", toolCallId: "c2" },
      { type: "assets", assetIds: ["x1", "x2", "x3"] },
      { type: "approval", approvalId: "i1" },
      { type: "approval", approvalId: "i2" },
      { type: "error", message: "Provider timeout", retryable: true },
    ] },
  ],
  todos: [{ content: "Research hooks", status: "completed" }, { content: "Write scripts", status: "in_progress" }, { content: "Generate videos", status: "pending" }],
  toolCalls: {
    c1: { id: "c1", name: "web_search", args: { query: "clean skincare ugc hooks" }, agent: "orchestrator", parentCallId: null, status: "complete", output: "12 results", startedAt: t },
    c2: { id: "c2", name: "write_file", args: { file_path: "/research/hook-patterns.md", content: "..." }, agent: "orchestrator", parentCallId: null, status: "running", startedAt: t },
    c3: { id: "c3", name: "fetch_url", args: { url: "https://example.com/a" }, agent: "research-analyst", parentCallId: "s1", status: "complete", startedAt: t },
  },
  subagents: { s1: { id: "s1", name: "research-analyst", task: "Collect trending hooks", status: "complete", model: "kimi-k2", toolCallIds: ["c3"], text: "", result: "Top hooks: problem-first, reveal.", startedAt: t, parentMessageId: "a1" } },
  assets: { x1: asset("x1", "completed"), x2: asset("x2", "in_progress"), x3: asset("x3", "failed", "live") },
  approvals: {
    i1: ap("i1", "publish_post", { account: "@glowco", caption: "Clean glow #ad", paid: true, schedule: { at: "tomorrow" } }),
    i2: ap("i2", "generate_media", { prompt: "serum unboxing", count: 3 }, 1.2),
  },
};

// TEST-ONLY UiEvent timelines (imported by *.test.ts, never by app code). `sampleRun` ends at an
// approval; `sampleResume` finishes the job.
import type { Asset, Decision, EventBase, UiEvent } from "@ugecy/contracts";

type Body<T extends UiEvent["type"]> = Omit<Extract<UiEvent, { type: T }>, keyof EventBase | "type">;
type Who = { agent?: string; parent?: string };

const svg = (label: string, hue: number) =>
  "data:image/svg+xml;utf8," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640" viewBox="0 0 360 640">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${hue} 60% 38%)"/>` +
    `<stop offset="1" stop-color="hsl(${hue + 50} 55% 22%)"/></linearGradient></defs><rect width="360" height="640" fill="url(#g)"/>` +
    `<text x="180" y="330" fill="white" fill-opacity=".85" font-family="sans-serif" font-size="22" text-anchor="middle">${label}</text></svg>`);

function builder(threadId: string, runId: string) {
  let seq = 0;
  const out: UiEvent[] = [];
  const ev = <T extends UiEvent["type"]>(type: T, body: Body<T>, who: Who = {}) => {
    out.push({
      seq: ++seq, ts: new Date().toISOString(), thread_id: threadId, run_id: runId,
      agent: who.agent ?? "orchestrator", ns: who.parent ? [`tools:${who.parent}`] : [], parent_call_id: who.parent ?? null,
      type, ...body,
    } as unknown as UiEvent);
  };
  return { out, ev };
}

const words = (text: string) => text.match(/\S+\s*/g) ?? [];

export function sampleRun(threadId: string, userText: string): UiEvent[] {
  const { out, ev } = builder(threadId, `run-${Date.now()}`);
  const R = { agent: "research-analyst", parent: "call-r1" };
  const C = { agent: "creative-strategist", parent: "call-c1" };
  const say = (id: string, text: string, who?: Who) => words(text).forEach((w) => ev("message.delta", { message_id: id, text: w }, who));

  ev("run.started", { model: "@cf/zai-org/glm-5.3" });
  words("The operator wants hooks that work. I should plan first, then delegate research, then script, then ask before generating media.")
    .forEach((w) => ev("reasoning.delta", { message_id: "m1", text: w }));
  say("m1", `Got it: "${userText.slice(0, 80)}". I'll plan the work, research public examples, then draft scripts.\n\n`);
  ev("tool.started", { call_id: "call-t1", name: "write_todos", args: {} });
  ev("todos.updated", { todos: [
    { content: "Research top hooks in the niche", status: "in_progress" },
    { content: "Draft 3 script variants", status: "pending" },
    { content: "Generate media (needs approval)", status: "pending" },
  ] });
  ev("tool.completed", { call_id: "call-t1", name: "write_todos", status: "ok", output_preview: "Updated 3 todos" });

  ev("tool.started", { call_id: "call-r1", name: "task", args: { subagent_type: "research-analyst", description: "Find the strongest public skincare UGC hooks this month" } });
  ev("subagent.started", { call_id: "call-r1", subagent: "research-analyst", description: "Find the strongest public skincare UGC hooks this month" });
  say("r-m1", "Searching TikTok and the open web for permitted public examples.\n", R);
  ev("tool.started", { call_id: "w1", name: "web_search", args: { query: "clean skincare ugc hooks tiktok", platform: "tiktok" } }, R);
  ev("tool.completed", { call_id: "w1", name: "web_search", status: "ok", output_preview: "8 results" }, R);
  const srcs = [
    ["https://www.tiktok.com/@skinlab/video/1", "I tried 30 days of one serum", "tiktok"],
    ["https://www.youtube.com/watch?v=abc", "Why this hook format converts", "youtube"],
    ["https://example.com/blog/ugc-hooks", "12 UGC hook formulas", "web"],
  ] as const;
  for (const [url, title, platform] of srcs) ev("source.added", { source: { url, title, platform, snippet: null } }, R);
  ev("tool.started", { call_id: "f1", name: "fetch_page", args: { url: srcs[2][0] } }, R);
  ev("tool.completed", { call_id: "f1", name: "fetch_page", status: "ok", output_preview: "# 12 UGC hook formulas\n1. Problem callout…" }, R);
  ev("tool.started", { call_id: "f2", name: "fetch_page", args: { url: "https://blocked.example.com/x" } }, R);
  ev("tool.completed", { call_id: "f2", name: "fetch_page", status: "error", output_preview: "403 Forbidden: robots.txt disallows fetching this page" }, R);
  ev("tool.started", { call_id: "w2", name: "write_file", args: { file_path: "/research/skincare-hooks.md" } }, R);
  ev("files.updated", { files: [{ path: "/research/skincare-hooks.md", size: 2140, modified_at: new Date().toISOString() }] }, R);
  ev("tool.completed", { call_id: "w2", name: "write_file", status: "ok", output_preview: "Wrote /research/skincare-hooks.md" }, R);
  ev("subagent.completed", { call_id: "call-r1", subagent: "research-analyst", status: "ok", summary: "Top patterns: problem callout, 30-day proof, ingredient myth-bust." });
  ev("tool.completed", { call_id: "call-r1", name: "task", status: "ok", output_preview: "Top patterns: problem callout, 30-day proof, ingredient myth-bust." });
  ev("todos.updated", { todos: [
    { content: "Research top hooks in the niche", status: "completed" },
    { content: "Draft 3 script variants", status: "in_progress" },
    { content: "Generate media (needs approval)", status: "pending" },
  ] });

  ev("tool.started", { call_id: "call-c1", name: "task", args: { subagent_type: "creative-strategist", description: "Draft 3 original 30s scripts from the research" } });
  ev("subagent.started", { call_id: "call-c1", subagent: "creative-strategist", description: "Draft 3 original 30s scripts from the research" });
  say("c-m1", "Writing three original scripts with an #ad disclosure line.\n", C);
  ev("tool.started", { call_id: "w3", name: "write_file", args: { file_path: "/scripts/serum-v1.md" } }, C);
  ev("files.updated", { files: [
    { path: "/research/skincare-hooks.md", size: 2140, modified_at: new Date().toISOString() },
    { path: "/scripts/serum-v1.md", size: 1480, modified_at: new Date().toISOString() },
  ] }, C);
  ev("tool.completed", { call_id: "w3", name: "write_file", status: "ok", output_preview: "Wrote /scripts/serum-v1.md" }, C);
  ev("subagent.completed", { call_id: "call-c1", subagent: "creative-strategist", status: "ok", summary: "3 scripts drafted." }, {});
  ev("tool.completed", { call_id: "call-c1", name: "task", status: "ok", output_preview: "3 scripts drafted." });

  say("m2", "Research and scripts are ready. Next I'd like to generate one vertical video, which costs money, so I need your approval.\n");
  ev("message.completed", { message_id: "m2", text: "" });
  ev("tool.started", { call_id: "g1", name: "generate_media", args: { kind: "video", prompt: "Handheld UGC, woman applies serum, 'day 30' caption", model: "higgsfield-ai/soul/v2/standard", count: 1 } },
    { agent: "production-coordinator" });
  ev("approval.requested", { interrupt_id: "int-1", requests: [{
    tool: "generate_media", agent: "production-coordinator",
    args: { kind: "video", prompt: "Handheld UGC, woman applies serum, 'day 30' caption", model: "higgsfield-ai/soul/v2/standard", count: 1 },
    description: "Generate 1 vertical video", allowed_decisions: ["approve", "edit", "reject"], estimated_cost_usd: 0.6,
  }] });
  ev("run.completed", { status: "interrupted" });
  return out;
}

export function sampleResume(threadId: string, decisions: Decision[]): UiEvent[] {
  const { out, ev } = builder(threadId, `run-${Date.now()}-b`);
  const rejected = decisions[0]?.type === "reject";
  ev("run.started", { model: "@cf/zai-org/glm-5.3" });
  if (rejected) {
    ev("message.delta", { message_id: "m3", text: "Understood, I skipped media generation. The scripts are in /scripts if you want to revisit." });
  } else {
    ev("tool.completed", { call_id: "g1", name: "generate_media", status: "ok", output_preview: "job queued" }, { agent: "production-coordinator" });
    const base: Asset = {
      id: "asset-1", thread_id: threadId, kind: "video", status: "queued", provider: "higgsfield", model: "higgsfield-ai/soul/v2/standard",
      prompt: "Handheld UGC, woman applies serum", url: null, thumbnail_url: null, job_id: "job-1", mode: "live", estimated_usd: 0.6,
      created_at: new Date().toISOString(),
    };
    ev("asset.updated", { asset: base });
    ev("progress", { tool: "generate_media", message: "Rendering video…" });
    ev("asset.updated", { asset: { ...base, status: "in_progress" } });
    ev("asset.updated", { asset: { ...base, status: "completed", thumbnail_url: svg("Video", 280), url: svg("Video", 280) } });
    words("The video finished. Nothing was posted.")
      .forEach((w) => ev("message.delta", { message_id: "m3", text: w }));
  }
  ev("message.completed", { message_id: "m3", text: "" });
  ev("run.completed", { status: "done" });
  return out;
}

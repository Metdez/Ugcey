// Dev/preview fixtures covering every tab. Not imported by production code.
import type { ThreadSnapshot } from "@/types/agent";
import type { Asset, AuditEntry, ApprovalRecord, DeviceStatus, MemoryFile, AppConfig } from "@ugecy/contracts";

const ago = (s: number) => new Date(Date.now() - s * 1000).toISOString();

export const thread: Partial<ThreadSnapshot> = {
  threadId: "t1", title: "Serum campaign", status: "idle",
  todos: [
    { content: "Research top skincare hooks", status: "completed" },
    { content: "Extract hook patterns", status: "completed" },
    { content: "Write 5 scripts", status: "completed" },
    { content: "Generate videos for script #2", status: "in_progress" },
    { content: "Review compliance", status: "pending" },
    { content: "Schedule posts", status: "pending" },
    { content: "Report performance", status: "pending" },
  ],
  toolCalls: {
    c1: { id: "c1", name: "fetch_trending_videos", args: {}, agent: "research-analyst", parentCallId: "s1", status: "complete", startedAt: ago(90) },
    c2: { id: "c2", name: "write_file", args: {}, agent: "research-analyst", parentCallId: "s1", status: "complete", startedAt: ago(60) },
  },
  subagents: {
    s1: { id: "s1", name: "research-analyst", task: "Find the top 20 TikTok UGC hooks for clean skincare this month and explain why they work.", status: "complete", model: "@cf/zai-org/glm-5.3", toolCallIds: ["c1", "c2"], text: "Scanning trending videos...", result: "Found **20 hooks**.\n\n- Problem-first openers\n- Before/after reveals", startedAt: ago(120), endedAt: ago(40), parentMessageId: "m1" },
    s2: { id: "s2", name: "creative-director", task: "Write 5 original 30-second scripts using the top patterns.", status: "running", model: "@cf/zai-org/glm-5.3", toolCallIds: [], text: "", startedAt: ago(30), parentMessageId: "m1" },
  },
  files: [
    { path: "/plans/campaign.md", size: 800, modified_at: ago(300) },
    { path: "/research/hook-patterns.md", size: 2400, modified_at: ago(100) },
    { path: "/scripts/script-1.md", size: 900, modified_at: ago(50) },
    { path: "/assets/manifest.json", size: 120, modified_at: ago(20) },
  ],
  sources: [
    { url: "https://www.tiktok.com/@glow/video/1", title: "Glow routine in 30s", platform: "tiktok", snippet: "Hook: 'stop doing this to your skin'" },
    { url: "https://www.youtube.com/watch?v=abc", title: "Skincare myths", platform: "youtube", snippet: "Long-form explainer with strong cold open." },
    { url: "https://example.com/blog/ugc", title: "UGC hooks that convert", platform: "web", snippet: null },
  ],
  assets: {
    a1: { id: "a1", thread_id: "t1", kind: "image", status: "completed", provider: "mock", model: "m", prompt: "serum", url: null, thumbnail_url: null, job_id: null, mode: "mock", estimated_usd: 0, created_at: ago(60) },
    a2: { id: "a2", thread_id: "t1", kind: "video", status: "in_progress", provider: "mock", model: "m", prompt: "ugc", url: null, thumbnail_url: null, job_id: null, mode: "mock", estimated_usd: 0.4, created_at: ago(30) },
  },
  approvals: {
    p1: { interrupt_id: "p1", thread_id: "t1", status: "pending", created_at: ago(20), requests: [{ tool: "publish_post", agent: "publishing", args: { caption: "Hi" }, description: "Publish 1 video", allowed_decisions: ["approve", "reject"] }] },
  },
};

export const config = { version: "0", modes: { llm: "mock", media: "mock", device: "mock", publishing: "mock", research: "mock" }, models: [], starter_prompts: [],
  agents: [
    { name: "research-analyst", description: "Finds and analyzes public UGC.", model: "@cf/zai-org/glm-5.3", tools: ["search", "fetch"], enabled: true },
    { name: "device-operator", description: "Operates a connected iPhone.", model: "@cf/zai-org/glm-5.3", tools: ["device_tap"], enabled: false },
  ] } satisfies AppConfig;

export const memories: MemoryFile[] = [
  { path: "/memories/brand-voice.md", scope: "memories", content: "Warm, direct, no medical claims.", updated_at: ago(3600), editable: true },
  { path: "/skills/ugc-hook-extraction/SKILL.md", scope: "skills", content: "Steps to extract hooks from videos.", updated_at: null, editable: false },
];

export const audit: AuditEntry[] = [
  { id: "u1", ts: ago(60), thread_id: "t1", actor: "agent", agent: "research-analyst", action: "tool_call", tool: "fetch_trending_videos", status: "ok", mode: "mock", detail: '{"count":24}' },
  { id: "u2", ts: ago(40), thread_id: "t1", actor: "operator", agent: null, action: "approval", tool: "publish_post", status: "rejected", mode: "mock", detail: "Rejected by operator" },
  { id: "u3", ts: ago(20), thread_id: "t1", actor: "agent", agent: "device-operator", action: "tool_call", tool: "device_tap", status: "error", mode: "mock", detail: "Device offline" },
];

export const approvalHistory: ApprovalRecord[] = [
  { interrupt_id: "h1", thread_id: "t0", status: "approved", created_at: ago(7200), decided_at: ago(7100), requests: [{ tool: "generate_video", agent: "production", args: {}, description: "", allowed_decisions: ["approve"] }] },
];

export const assetsRemote: Asset[] = [];

export const device: DeviceStatus = {
  provider: "mock", mode: "mock", control: "agent", last_action: "Tapping Post",
  devices: [{ id: "d1", name: "iPhone 15", kind: "iphone", status: "ready", ready: true }],
  session: { id: "ds1", device_id: "d1", goal: "Post the approved video to TikTok drafts", steps_used: 4, max_steps: 20 },
};

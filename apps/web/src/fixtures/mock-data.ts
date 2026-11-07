// Static data the shell needs when no backend is running (?mock=1).
import type { AppConfig, ConnectedAccount, ThreadSummary } from "@ugecy/contracts";

export const MOCK_CONFIG: AppConfig = {
  version: "mock",
  modes: { llm: "mock", media: "mock", device: "mock", publishing: "mock", research: "mock" },
  models: [
    { role: "orchestrator", model: "@cf/zai-org/glm-5.3" },
    { role: "research", model: "@cf/moonshotai/kimi-k3" },
    { role: "creative", model: "@cf/zai-org/glm-5.3" },
  ],
  agents: [
    { name: "orchestrator", description: "Plans and delegates", model: "@cf/zai-org/glm-5.3", tools: [], enabled: true },
    { name: "research-analyst", description: "Finds and analyses public UGC", model: "@cf/moonshotai/kimi-k3", tools: ["web_search", "fetch_page"], enabled: true },
    { name: "creative-strategist", description: "Scripts and hooks", model: "@cf/zai-org/glm-5.3", tools: ["write_file"], enabled: true },
  ],
  starter_prompts: [
    "Find the top 20 TikTok UGC hooks for clean skincare this month and explain why they work.",
    "Break these 5 videos into hook, script structure and CTA patterns.",
    "Write 5 original 30-second UGC scripts for our serum using the top patterns.",
    "Generate 3 vertical UGC-style videos for script #2 with Higgsfield.",
    "Schedule the approved videos to @glowco on TikTok and Instagram this week.",
    "How did last week's posts perform? What should we change?",
  ],
};

const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString();

export const MOCK_THREADS: ThreadSummary[] = [
  { id: "mock-1", title: "Clean skincare hook research", created_at: ago(30), updated_at: ago(5), status: "awaiting_approval" },
  { id: "mock-2", title: "Serum launch scripts", created_at: ago(26 * 60), updated_at: ago(25 * 60), status: "idle" },
  { id: "mock-3", title: "Weekly performance review", created_at: ago(4 * 24 * 60), updated_at: ago(4 * 24 * 60), status: "error" },
  { id: "mock-4", title: "Creator brief template", created_at: ago(20 * 24 * 60), updated_at: ago(20 * 24 * 60), status: "idle" },
];

export const MOCK_ACCOUNTS: ConnectedAccount[] = [
  { id: "a1", platform: "tiktok", handle: "@glowco", mode: "mock", status: "connected" },
  { id: "a2", platform: "instagram", handle: "@glowco", mode: "mock", status: "needs_auth" },
];

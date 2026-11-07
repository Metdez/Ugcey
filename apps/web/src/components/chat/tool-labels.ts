import type { ToolCallView } from "@/types/agent";

type S = ToolCallView["status"];
const str = (v: unknown) => (typeof v === "string" ? v : "");
const clip = (s: string, n = 60) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/** Sentence title for a tool line. The state is always in the text (a11y: no colour-only state). */
export function toolLabel(name: string, args: Record<string, unknown>, status: S): string {
  const path = str(args.file_path) || str(args.path);
  const q = str(args.query) || str(args.q);
  const url = str(args.url);
  const running = status === "running";
  if (status === "awaiting_approval") return `Waiting for approval: ${name.replace(/_/g, " ")}`;
  const failed = status === "error";
  const t = (run: string, done: string, fail: string) => (failed ? fail : running ? run : done);
  switch (name) {
    case "write_file":
      return t(`Writing ${path}…`, `Wrote ${path}`, `Failed to write ${path}`);
    case "edit_file":
      return t(`Editing ${path}…`, `Edited ${path}`, `Failed to edit ${path}`);
    case "read_file":
      return t(`Reading ${path}…`, `Read ${path}`, `Failed to read ${path}`);
    case "ls":
      return t("Listing files…", "Listed files", "Failed to list files");
    case "write_todos":
      return t("Updating the plan…", "Updated the plan", "Failed to update the plan");
    case "web_search": case "internet_search": case "search":
      return t(`Searching the web for ${clip(q)}…`, `Searched the web for ${clip(q)}`, `Search failed for ${clip(q)}`);
    case "fetch_url": case "web_fetch": case "scrape":
      return t(`Fetching ${clip(url)}…`, `Fetched ${clip(url)}`, `Failed to fetch ${clip(url)}`);
    case "generate_media":
      return t("Generating media…", "Generated media", "Failed to generate media");
    case "publish_post":
      return t("Publishing post…", "Published post", "Failed to publish post");
    case "task":
      return t("Delegating…", "Delegated", "Delegation failed");
    default: {
      const n = name.replace(/_/g, " ");
      return failed ? `Failed: ${n}` : running ? `Running ${name}…` : `Ran ${n}`;
    }
  }
}

/** First arg value that looks like a virtual file path (starts with "/"), for the Files link. */
export function toolFilePath(args: Record<string, unknown>): string | null {
  const p = str(args.file_path) || str(args.path);
  return p.startsWith("/") ? p : null;
}

const AGENT_VARS = ["research", "creative", "production", "publishing", "device", "analytics"];
/** CSS colour for an agent dot ("research-analyst" -> --agent-research). */
export function agentColor(agent: string): string {
  const k = AGENT_VARS.find((a) => agent.includes(a)) ?? "orchestrator";
  return `var(--agent-${k})`;
}

export const agentLabel = (agent: string) => {
  const s = agent.replace(/[-_]/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
};

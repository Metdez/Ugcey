import type { ApprovalRequest, Decision, DecisionType } from "@/types/agent";

/** Decisions every request in the interrupt allows (card-level buttons). */
export function allowedDecisions(requests: ApprovalRequest[]): DecisionType[] {
  const all: DecisionType[] = ["approve", "edit", "reject"];
  return all.filter((d) => requests.every((r) => r.allowed_decisions.includes(d)));
}

export const approveAll = (n: number): Decision[] => Array.from({ length: n }, () => ({ type: "approve" }));

export const rejectAll = (n: number, message: string): Decision[] =>
  Array.from({ length: n }, () => ({ type: "reject", message: message.trim() || undefined }));

/** Draft form value (string) -> typed arg, keyed on the original value's type. */
export function parseArg(original: unknown, raw: string | boolean): { value: unknown } | { error: string } {
  if (typeof original === "boolean") return { value: Boolean(raw) };
  if (typeof original === "number") {
    const n = Number(raw);
    return raw === "" || Number.isNaN(n) ? { error: "Enter a number" } : { value: n };
  }
  if (original !== null && typeof original === "object") {
    try { return { value: JSON.parse(String(raw)) }; } catch { return { error: "Invalid JSON" }; }
  }
  return { value: String(raw) };
}

/** Per-request drafts -> edit decisions, or per-field errors ("<requestIdx>.<key>"). */
export function editDecisions(
  requests: ApprovalRequest[], drafts: Array<Record<string, string | boolean>>,
): { decisions: Decision[] } | { errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const decisions = requests.map((r, i): Decision => {
    const args: Record<string, unknown> = {};
    for (const [k, orig] of Object.entries(r.args)) {
      const res = parseArg(orig, drafts[i]?.[k] ?? (typeof orig === "object" && orig !== null ? JSON.stringify(orig, null, 2) : (orig as string)));
      if ("error" in res) errors[`${i}.${k}`] = res.error; else args[k] = res.value;
    }
    return { type: "edit", args };
  });
  return Object.keys(errors).length ? { errors } : { decisions };
}

const MODEL_NAMES: Array<[string, string]> = [
  ["marketing-studio/image/flare", "Marketing Studio Flare"], ["marketing-studio/image/sunburst", "Marketing Studio Sunburst"],
  ["marketing-studio/image", "Marketing Studio"], ["higgsfield-ai/soul", "Soul"], ["higgsfield/ads-studio", "Ads Studio"],
  ["bytedance/seedance-2.5", "Seedance 2.5"], ["kling-video/v3.0", "Kling 3.0"], ["alibaba/wan-3.0", "Wan 3.0"],
];

/** Plain one-line summary of a request for the approval card: what it makes and with which model. */
export function requestSummary(r: ApprovalRequest): { title: string; prompt: string } {
  const a = r.args as Record<string, unknown>;
  const prompt = typeof a.prompt === "string" ? a.prompt : "";
  if (r.tool !== "generate_media") return { title: r.tool.replace(/_/g, " "), prompt };
  const model = String(a.model ?? "");
  const name = MODEL_NAMES.find(([id]) => model.startsWith(id))?.[1] ?? model;
  const opts = (a.args ?? {}) as Record<string, unknown>;
  const isImage = a.kind === "image" || model.startsWith("marketing-studio") || model.startsWith("higgsfield-ai/soul");
  const bits = [name, typeof opts.resolution === "string" ? opts.resolution : null].filter(Boolean).join(", ");
  const secs = typeof opts.duration === "number" ? `${opts.duration} s ` : "";
  return { title: `Generate ${isImage ? "an image" : `a ${secs}video`} (${bits})`, prompt };
}

/** "About $0.05", or a plain note when the provider gave no price. */
export const costLabel = (usd: number | null | undefined) =>
  usd == null ? "Price unknown" : usd < 0.01 ? "Under $0.01" : `About $${usd.toFixed(2)}`;

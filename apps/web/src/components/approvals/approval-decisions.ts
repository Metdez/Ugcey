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

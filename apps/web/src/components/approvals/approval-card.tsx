import { useState } from "react";
import { Clapperboard, Send, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import posthog from "@/lib/posthog";
import { cn } from "@/lib/utils";
import { threadActions, useThread } from "@/stores/thread-store";
import type { ApprovalRequest } from "@/types/agent";
import { allowedDecisions, approveAll, costLabel, editDecisions, rejectAll, requestSummary } from "./approval-decisions";
import { ApprovalEditForm, initialDraft, type Draft } from "./approval-edit-form";
import { ApprovalRejectForm } from "./approval-reject-form";

const icon = (tool: string): LucideIcon =>
  tool === "generate_media" ? Clapperboard : tool === "publish_post" ? Send : tool.startsWith("device_") ? Smartphone : ShieldCheck;

const preview = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v));

function ArgsPreview({ r }: { r: ApprovalRequest }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
      {Object.entries(r.args).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-xs text-muted-foreground">{k}</dt>
          <dd className="line-clamp-3 break-words">{preview(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ApprovalCard({ approvalId, variant }: { approvalId: string; variant: "inline" | "panel" }) {
  const rec = useThread((s) => s.approvals[approvalId]);
  const [mode, setMode] = useState<"view" | "edit" | "reject">("view");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (!rec) return null;
  const n = rec.requests.length;
  const dense = variant === "panel";

  if (rec.status !== "pending") {
    const t = rec.requests[0];
    const verb = { approved: "Approved", edited: "Approved (edited)", rejected: "Rejected", expired: "Expired" }[rec.status];
    return (
      <p className="py-1 text-[13px] text-muted-foreground">
        {verb}: {t ? requestSummary(t).title : "request"}{n > 1 ? ` (+${n - 1})` : ""}
        {rec.decided_at && ` · ${new Date(rec.decided_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
      </p>
    );
  }

  const allowed = allowedDecisions(rec.requests);
  const submit = async (d: Parameters<typeof threadActions.decide>[1]) => {
    setBusy(true);
    try {
      await threadActions.decide(approvalId, d);
      posthog.capture("approval_decided", { decision: d[0]?.type, request_count: d.length });
    } finally { setBusy(false); }
  };
  const startEdit = () => { setDrafts(rec.requests.map(initialDraft)); setErrors({}); setMode("edit"); };
  const saveEdit = () => {
    const res = editDecisions(rec.requests, drafts);
    if ("errors" in res) setErrors(res.errors); else void submit(res.decisions);
  };
  const cost = rec.requests.reduce((a, r) => a + (r.estimated_cost_usd ?? 0), 0);

  return (
    <section aria-label="Approval needed" tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && mode === "view" && allowed.includes("approve") && !busy) { e.preventDefault(); void submit(approveAll(n)); } }}
      className={cn("rounded-lg border border-l-[3px] border-l-warning bg-card focus-visible:ring-2 focus-visible:ring-ring", dense ? "p-2" : "p-3")}>
      <div className="flex flex-col gap-3">
        {rec.requests.map((r, i) => {
          const Icon = icon(r.tool);
          const s = requestSummary(r);
          return (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="flex items-start gap-2">
                <Icon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                <p className={cn("min-w-0 flex-1 font-semibold", dense ? "text-[13px]" : "text-sm")}>{s.title}</p>
                <Badge variant="outline" className="shrink-0 tabular-nums">{costLabel(r.estimated_cost_usd)}</Badge>
              </div>
              {s.prompt && mode !== "edit" && <p className="line-clamp-2 pl-6 text-[13px] text-muted-foreground">{s.prompt}</p>}
              {mode === "edit"
                ? <ApprovalEditForm request={r} idx={i} draft={drafts[i] ?? {}} errors={errors}
                    onChange={(k, v) => setDrafts((d) => d.map((x, j) => (j === i ? { ...x, [k]: v } : x)))} />
                : (
                  <details className="pl-6 text-xs text-muted-foreground">
                    <summary className="w-fit cursor-pointer select-none hover:text-foreground">Details</summary>
                    <div className="pt-2"><ArgsPreview r={r} /></div>
                  </details>
                )}
            </div>
          );
        })}
        {n > 1 && cost > 0 && <p className="text-xs text-muted-foreground tabular-nums">Total estimated cost ~${cost.toFixed(2)}</p>}
        {mode === "reject" && <ApprovalRejectForm reason={reason} onReason={setReason} text={note} onText={setNote} />}
        <div className="flex flex-wrap items-center justify-end gap-2">
          {mode !== "view" && <Button variant="ghost" size="sm" onClick={() => setMode("view")} disabled={busy}>Cancel</Button>}
          {mode === "view" && allowed.includes("reject") && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setMode("reject")}>Reject</Button>}
          {mode === "view" && allowed.includes("edit") && <Button variant="outline" size="sm" onClick={startEdit}>Edit</Button>}
          {mode === "view" && allowed.includes("approve") && (
            <Button size="sm" disabled={busy} onClick={() => void submit(approveAll(n))}>Approve <Kbd>⌘↵</Kbd></Button>
          )}
          {mode === "edit" && <Button size="sm" disabled={busy} onClick={saveEdit}>Approve with edits</Button>}
          {mode === "reject" && (
            <Button size="sm" variant="destructive" disabled={busy}
              onClick={() => void submit(rejectAll(n, [reason, note].filter(Boolean).join(": ")))}>Reject</Button>
          )}
        </div>
      </div>
    </section>
  );
}

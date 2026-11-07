import { Download, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";
import { AuditRow } from "@/components/audit/audit-row";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { Chips } from "../chips";
import { EmptyState } from "../empty";
import { download, usePoll } from "../hooks";
import { filterAudit, type AuditFilter } from "../lib";

const FILTERS = [
  { value: "all", label: "All" }, { value: "ok", label: "OK" }, { value: "error", label: "Errors" },
  { value: "pending", label: "Pending" }, { value: "rejected", label: "Rejected" },
] as const;

export default function AuditTab() {
  const threadId = useThread((s) => s.threadId);
  const focusId = useUi((s) => (s.focus?.kind === "audit" ? s.focus.id : null));
  const [live, setLive] = useState(true);
  const [status, setStatus] = useState<AuditFilter>("all");
  const { data, error, refresh } = usePoll(() => api.listAudit(threadId ?? undefined, 200), 5000, live);
  const rows = useMemo(() => filterAudit(data ?? [], status), [data, status]);

  if (data && !data.length) return <EmptyState icon={ScrollText}>Every tool call, approval and external action is logged here.</EmptyState>;
  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex items-center gap-3">
        <Label className="flex items-center gap-2 text-xs"><Switch checked={live} onCheckedChange={(v) => { setLive(v); if (v) void refresh(); }} />Live</Label>
        <Button variant="outline" size="sm" className="ml-auto" disabled={!rows.length}
          onClick={() => download("ugecy-audit.json", JSON.stringify(rows, null, 2), "application/json")}><Download />Export JSON</Button>
      </div>
      <Chips label="Status" value={status} onChange={setStatus} options={FILTERS} />
      {error && <p role="alert" className="text-xs text-destructive">Audit unavailable: {error}</p>}
      <ul>{rows.map((r) => <AuditRow key={r.id} row={r} focused={focusId === r.id} />)}</ul>
      {data && !rows.length && <p className="text-xs text-muted-foreground">No entries with this status.</p>}
    </div>
  );
}

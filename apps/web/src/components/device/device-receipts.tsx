import { AuditRow } from "@/components/audit/audit-row";
import type { AuditEntry } from "@/types/agent";

export function DeviceReceipts({ rows }: { rows: AuditEntry[] }) {
  if (!rows.length) return <p className="text-xs text-muted-foreground">No device actions recorded yet.</p>;
  return <ul>{rows.map((r) => <AuditRow key={r.id} row={r} focused={false} />)}</ul>;
}

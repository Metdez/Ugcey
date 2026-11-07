import { Smartphone } from "lucide-react";
import { useMemo } from "react";
import { DeviceReceipts } from "@/components/device/device-receipts";
import { GlasshandDisconnected, GlasshandFailed, GlasshandPending } from "@/components/device/glasshand-connect";
import { GlasshandPanel } from "@/components/device/glasshand-panel";
import { useGlasshand } from "@/components/device/use-glasshand";
import { Badge } from "@/components/ui/badge";
import { viewState } from "@/lib/glasshand";
import { api } from "@/lib/api";
import { EmptyState } from "../empty";
import { usePoll } from "../hooks";
import { filterAudit, isDeviceRow } from "../lib";

export default function DeviceTab() {
  const { data: dev, error } = usePoll(() => api.getDevice(), 2000);
  const { data: audit } = usePoll(() => api.listAudit(undefined, 100), 5000);
  const gh = useGlasshand();
  const receipts = useMemo(() => filterAudit((audit ?? []).filter(isDeviceRow), "all").slice(0, 10), [audit]);

  if (error && !dev) return <EmptyState icon={Smartphone}>Device status unavailable: {error}</EmptyState>;
  if (!dev) return <p className="p-3 text-xs text-muted-foreground">Loading…</p>;
  const s = dev.session;
  const view = viewState(gh.status);
  return (
    <div className="flex flex-col gap-4 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-semibold capitalize">{dev.provider}</span>
        {dev.mode === "off" && <Badge variant="secondary">not connected</Badge>}
        <Badge variant="outline">control: {dev.control}</Badge>
      </div>
      {dev.last_action && <p className="text-xs text-muted-foreground">Last action: {dev.last_action}</p>}
      {view === "connected" && gh.status ? <GlasshandPanel status={gh.status} busy={gh.busy} onSelect={gh.select} onDisconnect={gh.disconnect} />
        : (
          view === "pending" ? <GlasshandPending status={gh.status} busy={gh.busy} onCancel={gh.disconnect} />
              : view === "failed" ? <GlasshandFailed status={gh.status} busy={gh.busy} onConnect={gh.connect} />
              : <GlasshandDisconnected busy={gh.busy} error={gh.error} onConnect={gh.connect} />
        )}
      {s ? (
        <section className="flex flex-col gap-1 rounded-lg border p-2.5 text-xs">
          <p className="text-[13px]">{s.goal}</p>
          <p className="tabular-nums text-muted-foreground">Steps {s.steps_used}/{s.max_steps}</p>
        </section>
      ) : <EmptyState icon={Smartphone}>No device session. The device operator asks for approval before it connects.</EmptyState>}
      <section className="flex flex-col gap-1.5">
        <h3 className="text-xs font-medium text-muted-foreground">Receipts</h3>
        <DeviceReceipts rows={receipts} />
      </section>
    </div>
  );
}

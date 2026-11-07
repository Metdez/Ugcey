import { Brain, Info } from "lucide-react";
import { MemoryAdd } from "@/components/memory/memory-add";
import { MemoryRow } from "@/components/memory/memory-row";
import { api } from "@/lib/api";
import { EmptyState } from "../empty";
import { usePoll } from "../hooks";

export default function MemoryTab() {
  const { data, error, refresh } = usePoll(() => api.listMemories(), 30_000);
  const mem = (data ?? []).filter((m) => m.scope === "memories");
  const skills = (data ?? []).filter((m) => m.scope === "skills");
  return (
    <div className="flex flex-col gap-3 p-3">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Info className="size-3.5" />Memory changes apply to new threads</p>
      <MemoryAdd onAdded={refresh} />
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {data && !data.length && <EmptyState icon={Brain}>Nothing remembered yet. Add brand rules or preferences.</EmptyState>}
      {mem.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-xs font-medium text-muted-foreground">Long-term (/memories)</h3>
          <ul className="flex flex-col gap-1.5">{mem.map((m) => <MemoryRow key={m.path} file={m} onSaved={refresh} />)}</ul>
        </section>
      )}
      {skills.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-xs font-medium text-muted-foreground">Playbooks (/skills)</h3>
          <ul className="flex flex-col gap-1.5">{skills.map((m) => <MemoryRow key={m.path} file={m} onSaved={refresh} />)}</ul>
        </section>
      )}
    </div>
  );
}

import { Badge } from "@/components/ui/badge";
import { usePoll } from "../inspector/hooks";
import { agentColor } from "../inspector/lib";
import { api } from "@/lib/api";

export function AgentRoster() {
  const { data, error } = usePoll(() => api.getConfig(), 60_000);
  if (error) return <p className="text-xs text-muted-foreground">Team roster unavailable: {error}</p>;
  if (!data) return null;
  return (
    <ul className="flex flex-col gap-1.5">
      {data.agents.map((a) => (
        <li key={a.name} className={`flex flex-col gap-1 rounded-lg border p-2.5 ${a.enabled ? "" : "opacity-60"}`}>
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: agentColor(a.name) }} aria-hidden />
            <span className="flex-1 truncate text-[13px] font-medium">{a.name}</span>
            <Badge variant={a.enabled ? "secondary" : "outline"}>{a.enabled ? "enabled" : "disabled"}</Badge>
          </span>
          <span className="text-xs text-muted-foreground">{a.description}</span>
          <span className="font-mono text-[11px] text-muted-foreground">{a.model.split("/").pop()} · {a.tools.length} tools</span>
        </li>
      ))}
    </ul>
  );
}

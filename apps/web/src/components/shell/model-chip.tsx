import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useWorkspace } from "@/stores/workspace-store";

const short = (m: string) => m.split("/").pop() ?? m;

export function ModelChip() {
  const config = useWorkspace((s) => s.config);
  const main = config?.models.find((m) => m.role === "orchestrator") ?? config?.models[0];
  if (!main) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="rounded-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none" aria-label="Models in use">
          <Badge variant="outline" className="gap-1 font-mono text-[11px]">{short(main.model)}<ChevronDown className="size-3" /></Badge>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 text-xs">
        <p className="mb-2 text-sm font-semibold">Models</p>
        <ul className="space-y-1">
          {config!.agents.filter((a) => a.enabled).map((a) => (
            <li key={a.name} className="flex justify-between gap-3">
              <span>{a.name}</span><span className="truncate font-mono text-muted-foreground">{short(a.model)}</span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

import { ChevronRight, FileText } from "lucide-react";
import type { FileEntry } from "@/types/agent";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useFlash } from "../inspector/hooks";
import { groupFiles } from "../inspector/lib";

function Leaf({ entry, name, selected, onSelect }: { entry: FileEntry; name: string; selected: boolean; onSelect: () => void }) {
  const flash = useFlash(selected);
  return (
    <button
      ref={flash.ref as React.Ref<HTMLButtonElement>}
      onClick={onSelect}
      aria-current={selected}
      className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left font-mono text-xs hover:bg-accent ${selected ? "bg-accent" : ""} ${flash.className}`}
    >
      <FileText className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{name}</span>
    </button>
  );
}

export function FileTree({ files, selected, onSelect }: { files: FileEntry[]; selected: string | null; onSelect: (path: string) => void }) {
  return (
    <div className="flex flex-col gap-0.5" role="tree" aria-label="Agent files">
      {groupFiles(files).map((g) => (
        <Collapsible key={g.group} defaultOpen>
          <CollapsibleTrigger className="group flex w-full items-center gap-1 px-1 py-1 font-mono text-xs text-muted-foreground">
            <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
            {g.group} <span className="tabular-nums">({g.files.length})</span>
          </CollapsibleTrigger>
          <CollapsibleContent className="pl-3">
            {g.files.map(({ entry, name }) => (
              <Leaf key={entry.path} entry={entry} name={name} selected={selected === entry.path} onSelect={() => onSelect(entry.path)} />
            ))}
          </CollapsibleContent>
        </Collapsible>
      ))}
    </div>
  );
}

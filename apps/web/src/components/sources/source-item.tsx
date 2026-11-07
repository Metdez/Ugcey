import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Source } from "@/types/agent";
import { useFlash } from "../inspector/hooks";
import { domainOf } from "../inspector/lib";

export function SourceItem({ source, focused }: { source: Source; focused: boolean }) {
  const flash = useFlash(focused);
  const domain = domainOf(source.url);
  return (
    <li ref={flash.ref as React.Ref<HTMLLIElement>} className={`flex gap-2 rounded-lg border bg-card p-2.5 ${flash.className}`}>
      <img src={`https://icons.duckduckgo.com/ip3/${domain}.ico`} alt="" width={16} height={16} className="mt-0.5 size-4 shrink-0 rounded-sm" loading="lazy" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <a href={source.url} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1 text-[13px] font-medium hover:underline">
          <span className="truncate">{source.title || domain}</span><ExternalLink className="size-3 shrink-0" aria-hidden />
        </a>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="truncate">{domain}</span>
          {source.platform && <Badge variant="secondary">{source.platform}</Badge>}
        </span>
        {source.snippet && <p className="line-clamp-2 text-xs text-muted-foreground">{source.snippet}</p>}
      </div>
    </li>
  );
}

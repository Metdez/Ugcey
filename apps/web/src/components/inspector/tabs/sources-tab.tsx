import { Globe } from "lucide-react";
import { useMemo, useState } from "react";
import { SourceItem } from "@/components/sources/source-item";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { Chips } from "../chips";
import { EmptyState } from "../empty";

const PLATFORMS = [
  { value: "all", label: "All" }, { value: "tiktok", label: "TikTok" }, { value: "instagram", label: "IG" },
  { value: "youtube", label: "YT" }, { value: "web", label: "Web" },
] as const;
type P = (typeof PLATFORMS)[number]["value"];

export default function SourcesTab() {
  const sources = useThread((s) => s.sources);
  const focusUrl = useUi((s) => (s.focus?.kind === "source" ? s.focus.id : null));
  const [platform, setPlatform] = useState<P>("all");
  const shown = useMemo(
    () => sources.filter((s) => platform === "all" || (s.platform ?? "web") === platform),
    [sources, platform],
  );
  if (!sources.length) return <EmptyState icon={Globe}>Videos and pages the agent analyzes appear here.</EmptyState>;
  return (
    <div className="flex flex-col gap-3 p-3">
      <Chips label="Platform" value={platform} onChange={setPlatform} options={PLATFORMS} />
      {shown.length ? <ul className="flex flex-col gap-1.5">{shown.map((s) => <SourceItem key={s.url} source={s} focused={focusUrl === s.url} />)}</ul>
        : <p className="text-xs text-muted-foreground">No sources for this platform.</p>}
      <p className="border-t pt-2 text-[11px] text-muted-foreground">Analyzed for patterns only — never re-published</p>
    </div>
  );
}

import { Images } from "lucide-react";
import { useMemo, useState } from "react";
import { AssetThumb } from "@/components/chat";
import { api } from "@/lib/api";
import { useThread } from "@/stores/thread-store";
import { Chips } from "../chips";
import { EmptyState } from "../empty";
import { usePoll } from "../hooks";

const KINDS = [{ value: "all", label: "All" }, { value: "image", label: "Images" }, { value: "video", label: "Videos" }] as const;
const STATUSES = [
  { value: "all", label: "Any status" }, { value: "completed", label: "Done" },
  { value: "in_progress", label: "Generating" }, { value: "failed", label: "Failed" },
] as const;

export default function AssetsTab() {
  const threadAssets = useThread((s) => s.assets);
  const { data: remote } = usePoll(() => api.listAssets(), 15_000);
  const [kind, setKind] = useState<(typeof KINDS)[number]["value"]>("all");
  const [status, setStatus] = useState<(typeof STATUSES)[number]["value"]>("all");

  const assets = useMemo(() => {
    const merged = new Map((remote ?? []).map((a) => [a.id, a]));
    for (const a of Object.values(threadAssets)) merged.set(a.id, a); // live thread state wins
    return [...merged.values()]
      .filter((a) => (kind === "all" || a.kind === kind) && (status === "all" || a.status === status))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [remote, threadAssets, kind, status]);

  if (!remote?.length && !Object.keys(threadAssets).length) return <EmptyState icon={Images}>Generated images and videos appear here.</EmptyState>;
  return (
    <div className="flex flex-col gap-3 p-3">
      <Chips label="Type" value={kind} onChange={setKind} options={KINDS} />
      <Chips label="Status" value={status} onChange={setStatus} options={STATUSES} />
      {assets.length ? (
        <ul className="grid grid-cols-2 gap-2">
          {assets.map((a) => (
            <li key={a.id}><AssetThumb assetId={a.id} size="md" /></li>
          ))}
        </ul>
      ) : <p className="text-xs text-muted-foreground">No assets match these filters.</p>}
    </div>
  );
}

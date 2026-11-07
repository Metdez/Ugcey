import { AlertCircle, Clapperboard, Download } from "lucide-react";
import { useMemo } from "react";
import type { Asset } from "@ugecy/contracts";
import { RelativeTime } from "@/components/common/relative-time";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useThread } from "@/stores/thread-store";
import { EmptyState } from "../empty";
import { usePoll } from "../hooks";

/** A finished ad is the video the production agent renders for the whole script. Stills, product photos and
 *  other intermediate files are inputs, so this panel leaves them out. */
const isFinalOutput = (a: Asset) => a.kind === "video";

export default function AssetsTab() {
  const threadId = useThread((s) => s.threadId);
  const threadAssets = useThread((s) => s.assets);
  // Generation keeps running after the agent's turn ends, so poll this thread's assets for status changes.
  const { data: remote } = usePoll(() => (threadId ? api.listAssets(threadId) : Promise.resolve([])), 15_000, !!threadId);

  const ads = useMemo(() => {
    const merged = new Map((remote ?? []).map((a) => [a.id, a]));
    for (const a of Object.values(threadAssets)) {
      const polled = merged.get(a.id);
      // live stream events win unless the poll already has a newer, finished state
      if (!polled || polled.status === a.status || a.status === "completed" || a.status === "failed") merged.set(a.id, a);
    }
    // the poll result can still belong to the previous thread right after switching, so filter by thread
    return [...merged.values()].filter((a) => a.thread_id === threadId && isFinalOutput(a))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [remote, threadAssets, threadId]);

  if (!ads.length) return <EmptyState icon={Clapperboard}>Your finished ad appears here once it is generated.</EmptyState>;
  return (
    <ul className="flex flex-col gap-6 p-3" aria-label="Finished ads">
      {ads.map((a) => <li key={a.id}><FinalAd asset={a} /></li>)}
    </ul>
  );
}

function FinalAd({ asset }: { asset: Asset }) {
  const pending = asset.status === "queued" || asset.status === "in_progress";
  const failed = asset.status === "failed";
  return (
    <figure className="mx-auto flex w-full max-w-[22rem] flex-col gap-2">
      <div className={cn("relative aspect-[9/16] w-full overflow-hidden rounded-[1.75rem] bg-muted ring-1 ring-border",
        failed && "ring-destructive")}>
        {pending ? (
          <>
            <Skeleton className="absolute inset-0 rounded-none" />
            <p className="absolute inset-x-4 bottom-5 text-center text-[13px] leading-[18px] text-muted-foreground">
              Generating your ad. A 15 second ad usually takes 3 to 10 minutes.
            </p>
          </>
        ) : failed ? (
          <p className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-[13px] leading-[18px] text-destructive">
            <AlertCircle className="size-5" aria-hidden />
            Generation failed. Ask the agent to try this ad again.
          </p>
        ) : asset.url ? (
          <video src={asset.url} poster={asset.thumbnail_url ?? undefined} controls playsInline preload="metadata"
            aria-label="Finished ad" className="size-full bg-black object-cover" />
        ) : (
          <p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[13px] text-muted-foreground">
            The video file is no longer available.
          </p>
        )}
      </div>
      <figcaption className="flex items-center justify-between gap-2 px-1 text-xs text-muted-foreground">
        <span>
          {pending ? "Generating, started " : failed ? "Failed " : "Ready, made "}
          <RelativeTime iso={asset.created_at} />
          {asset.mode !== "live" && " (mock)"}
        </span>
        {asset.url && !pending && (
          <Button asChild variant="ghost" size="sm" className="h-7 px-2">
            <a href={asset.url} download target="_blank" rel="noopener noreferrer"><Download />Download</a>
          </Button>
        )}
      </figcaption>
    </figure>
  );
}

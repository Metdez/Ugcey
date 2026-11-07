import { AlertCircle, Music } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";

const SIZE = { sm: "w-16", md: "w-32", lg: "w-60" };

export function AssetThumb({ assetId, size = "md" }: { assetId: string; size?: "sm" | "md" | "lg" }) {
  const asset = useThread((s) => s.assets[assetId]);
  const open = useUi((s) => s.openLightbox);
  if (!asset) return null;
  const pending = asset.status === "queued" || asset.status === "in_progress";
  const src = asset.thumbnail_url ?? (asset.kind === "image" ? asset.url : null);
  return (
    <button type="button" onClick={() => open(assetId)} aria-label={`Open ${asset.kind}: ${asset.prompt}`}
      className={cn("group relative aspect-[9/16] shrink-0 overflow-hidden rounded-lg border bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        SIZE[size], asset.status === "failed" && "border-destructive")}>
      {pending ? (
        <>
          <Skeleton className="absolute inset-0 rounded-none" />
          {size !== "sm" && <span className="absolute inset-x-1 bottom-2 text-center text-[11px] text-muted-foreground">Generating with Higgsfield…</span>}
        </>
      ) : asset.status === "failed" ? (
        <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-destructive">
          <AlertCircle className="size-4" />Failed
        </span>
      ) : asset.kind === "video" && asset.url ? (
        <video src={asset.url} poster={asset.thumbnail_url ?? undefined} muted playsInline loop preload="metadata"
          className="size-full object-cover" onMouseEnter={(e) => void e.currentTarget.play().catch(() => {})}
          onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }} />
      ) : src ? (
        <img src={src} alt={asset.prompt} loading="lazy" className="size-full object-cover" />
      ) : (
        <Music className="absolute inset-0 m-auto size-5 text-muted-foreground" />
      )}
    </button>
  );
}

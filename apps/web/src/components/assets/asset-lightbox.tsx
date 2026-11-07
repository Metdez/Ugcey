import { Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";

/** Mounted once in AppShell; bound to useUi().lightboxAssetId. */
export function AssetLightbox() {
  const id = useUi((s) => s.lightboxAssetId);
  const close = useUi((s) => s.openLightbox);
  const asset = useThread((s) => (id ? s.assets[id] : undefined));
  return (
    <Dialog open={!!asset} onOpenChange={(o) => { if (!o) close(null); }}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-3xl">
        {asset && (
          <div className="grid gap-4 sm:grid-cols-[minmax(0,18rem)_1fr]">
            <div className="aspect-[9/16] overflow-hidden rounded-lg bg-muted">
              {!asset.url ? <p className="p-4 text-sm text-muted-foreground">Not ready yet ({asset.status}).</p>
                : asset.kind === "video" ? <video src={asset.url} poster={asset.thumbnail_url ?? undefined} controls playsInline className="size-full object-contain" />
                : asset.kind === "audio" ? <audio src={asset.url} controls className="w-full" />
                : <img src={asset.url} alt={asset.prompt} className="size-full object-contain" />}
            </div>
            <div className="flex flex-col gap-3">
              <DialogTitle>Asset preview</DialogTitle>
              <DialogDescription className="text-foreground">{asset.prompt}</DialogDescription>
              <div className="flex flex-wrap gap-1">
                <Badge variant="outline">{asset.model}</Badge>
                <Badge variant="outline">{asset.provider}</Badge>
                <Badge variant="outline">{asset.mode}</Badge>
                <Badge variant="outline">{asset.status}</Badge>
              </div>
              {asset.url && (
                <Button asChild variant="outline" size="sm" className="w-fit">
                  <a href={asset.url} download target="_blank" rel="noopener noreferrer"><Download />Download</a>
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

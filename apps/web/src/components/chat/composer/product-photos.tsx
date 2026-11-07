import { useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { threadActions } from "@/stores/thread-store";

export type ProductPhoto = { key: string; name: string; assetId?: string; url?: string | null; error?: string };

const ACCEPT = "image/jpeg,image/png,image/webp";

/** The line the agent reads to find the real product. Kept stable: the orchestrator prompt matches on it. */
const productPhotoLine = (photos: ProductPhoto[]) => {
  const done = photos.filter((p) => p.assetId);
  return done.length
    ? `Product photos attached: ${done.map((p) => p.assetId).join(", ")} (${done.map((p) => p.name).join(", ")}).`
    : "";
};

/** Attach button plus the chips for attached product photos. Uploading creates the thread if there is none. */
export function useProductPhotos(titleHint: () => string) {
  const [photos, setPhotos] = useState<ProductPhoto[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const patch = (key: string, p: Partial<ProductPhoto>) =>
    setPhotos((list) => list.map((x) => (x.key === key ? { ...x, ...p } : x)));

  const add = async (files: FileList | null) => {
    for (const file of Array.from(files ?? [])) {
      const key = `${file.name}-${file.size}-${Date.now()}`;
      setPhotos((list) => [...list, { key, name: file.name }]);
      try {
        const threadId = await threadActions.ensureThread(titleHint() || `Ad for ${file.name}`);
        const asset = await api.uploadProductPhoto(threadId, file);
        patch(key, { assetId: asset.id, url: asset.url });
      } catch (e) {
        patch(key, { error: e instanceof Error ? e.message : "Upload failed" });
      }
    }
    if (input.current) input.current.value = "";
  };

  const uploading = photos.some((p) => !p.assetId && !p.error);
  const pickerButton = (disabled: boolean) => (
    <>
      <input ref={input} type="file" accept={ACCEPT} multiple hidden onChange={(e) => void add(e.target.files)} />
      <Button size="icon" variant="ghost" aria-label="Attach product photo" title="Attach product photo"
        disabled={disabled} onClick={() => input.current?.click()}>
        <ImagePlus />
      </Button>
    </>
  );
  const chips = photos.length > 0 && (
    <ul aria-label="Attached product photos" className="flex flex-wrap gap-1.5 px-1 pb-1">
      {photos.map((p) => (
        <li key={p.key} className={`flex max-w-full items-center gap-1.5 rounded-lg border bg-muted/50 py-0.5 pr-0.5 pl-1 text-xs ${p.error ? "border-destructive text-destructive" : ""}`}>
          {p.url ? <img src={p.url} alt="" className="size-6 shrink-0 rounded object-cover" />
            : !p.error ? <Spinner className="size-4 shrink-0" /> : null}
          <span className="max-w-[16ch] truncate" title={p.error ? `${p.name}: ${p.error}` : p.name}>
            {p.error ? `Couldn't upload ${p.name}` : p.name}
          </span>
          <Button size="icon-xs" variant="ghost" aria-label={`Remove ${p.name}`}
            onClick={() => setPhotos((list) => list.filter((x) => x.key !== p.key))}><X /></Button>
        </li>
      ))}
    </ul>
  );
  return { line: productPhotoLine(photos), uploading, chips, pickerButton, clear: () => setPhotos([]) };
}

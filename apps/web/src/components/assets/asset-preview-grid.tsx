import { useUi } from "@/stores/ui-store";
import { AssetThumb } from "./asset-thumb";

export function AssetPreviewGrid({ assetIds }: { assetIds: string[] }) {
  const open = useUi((s) => s.openLightbox);
  if (!assetIds.length) return null;
  if (assetIds.length === 1) return <AssetThumb assetId={assetIds[0]} size="lg" />;
  const shown = assetIds.length > 4 ? assetIds.slice(0, 3) : assetIds;
  const extra = assetIds.length - shown.length;
  return (
    <div className="grid max-w-[16rem] grid-cols-2 gap-2">
      {shown.map((id) => <AssetThumb key={id} assetId={id} size="lg" />)}
      {extra > 0 && (
        <button type="button" onClick={() => open(assetIds[3])}
          className="flex aspect-[9/16] items-center justify-center rounded-lg border bg-muted text-lg font-semibold">+{extra}</button>
      )}
    </div>
  );
}

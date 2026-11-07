import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** iPhone-shaped frame; the screen is a polled screenshot (mock/mjpeg-less fallback). */
export function DeviceFrame({ caption }: { caption?: string | null }) {
  const [src, setSrc] = useState(() => api.deviceScreenshotUrl());
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) setSrc(api.deviceScreenshotUrl()); }, 2000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="mx-auto w-full max-w-[220px]">
      <div className="relative aspect-[393/852] overflow-hidden rounded-[3rem] border-[10px] border-neutral-900 bg-neutral-950">
        <div className="absolute left-1/2 top-2 z-10 h-[37px] w-[126px] -translate-x-1/2 rounded-full bg-black" aria-hidden />
        {failed ? <div className="flex h-full items-center justify-center p-4 text-center text-xs text-neutral-400">No screen available</div>
          : <img src={src} alt="Live device screen" className="size-full object-cover" onLoad={() => setFailed(false)} onError={() => setFailed(true)} />}
        {caption && <div className="absolute inset-x-2 bottom-3 rounded-md bg-black/70 px-2 py-1 text-center text-[11px] text-white">{caption}</div>}
      </div>
    </div>
  );
}

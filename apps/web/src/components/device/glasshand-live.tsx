import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cropRect, streamUrl, type Geometry } from "@/lib/glasshand";

const BACKOFF = [2000, 5000, 15000];

/** Live iPhone view: cropped JPEG frames from the relay, falling back to polled snapshots. */
export function GlasshandLive({ rentalId }: { rentalId: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const paused = useRef(false);
  const [isPaused, setPaused] = useState(false);
  const [live, setLive] = useState(false);
  const [fps, setFps] = useState(0);
  const [snap, setSnap] = useState(() => api.deviceScreenshotUrl());

  useEffect(() => {
    let ws: WebSocket | null = null, timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false, attempt = 0, busy = false, frames = 0;
    let geo: Geometry | null = null;
    const fpsTimer = setInterval(() => { setFps(frames); frames = 0; }, 1000);

    const draw = async (blob: Blob) => {
      const c = canvas.current;
      if (!c || !geo) return;
      busy = true;
      let bmp: ImageBitmap | undefined;
      try {
        bmp = await createImageBitmap(blob);
        const [vx, vy, vw, vh] = cropRect(geo, bmp.width, bmp.height);
        if (c.width !== vw || c.height !== vh) { c.width = vw; c.height = vh; }
        c.getContext("2d")?.drawImage(bmp, vx, vy, vw, vh, 0, 0, c.width, c.height);
        frames++;
      } catch { /* undecodable frame: skip */ } finally { bmp?.close(); busy = false; }
    };
    const open = () => {
      if (stopped) return;
      const s = new WebSocket(streamUrl());
      ws = s;
      s.binaryType = "blob";
      s.onmessage = (e) => {
        if (typeof e.data === "string") {
          try {
            const m = JSON.parse(e.data);
            if (m.type === "hello" && m.geometry) { geo = m.geometry; setLive(true); attempt = 0; }
            else if (m.type === "error") s.close();
          } catch { /* ignore malformed control message */ }
        } else if (!busy && !paused.current) void draw(e.data as Blob);
      };
      const fail = () => {
        if (stopped || ws !== s) return;
        ws = null; geo = null; setLive(false); setFps(0);
        timer = setTimeout(open, BACKOFF[Math.min(attempt++, BACKOFF.length - 1)]);
      };
      s.onerror = fail;
      s.onclose = fail;
    };
    open();
    return () => { stopped = true; clearTimeout(timer); clearInterval(fpsTimer); ws?.close(); };
  }, [rentalId]);

  useEffect(() => {
    if (live) return;
    const id = setInterval(() => { if (!document.hidden) setSnap(api.deviceScreenshotUrl()); }, 2000);
    return () => clearInterval(id);
  }, [live]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-2">
        {live ? <Badge variant="outline" className="gap-1.5"><span className="size-1.5 animate-pulse rounded-full bg-destructive" aria-hidden />LIVE · {isPaused ? "paused" : `${fps} fps`}</Badge>
          : <Badge variant="secondary">SNAPSHOTS</Badge>}
        {live && (
          <Button size="sm" variant="ghost" aria-pressed={isPaused} onClick={() => { paused.current = !paused.current; setPaused(paused.current); }}>
            {isPaused ? <Play aria-hidden /> : <Pause aria-hidden />}{isPaused ? "Resume stream" : "Pause stream"}
          </Button>
        )}
      </div>
      <div className="w-full max-w-[220px]">
        <div className="relative aspect-[393/852] overflow-hidden rounded-[3rem] border-[10px] border-neutral-900 bg-neutral-950">
          <div className="absolute left-1/2 top-2 z-10 h-[37px] w-[126px] -translate-x-1/2 rounded-full bg-black" aria-hidden />
          <canvas ref={canvas} aria-label="Live iPhone screen" role="img" className={live ? "size-full object-contain bg-neutral-100" : "hidden"} />
          {!live && <img src={snap} alt="iPhone screen snapshot" className="size-full object-contain bg-neutral-100" />}
        </div>
      </div>
      {!live && <p role="status" className="text-xs text-muted-foreground">Live stream unavailable — showing snapshots</p>}
    </div>
  );
}

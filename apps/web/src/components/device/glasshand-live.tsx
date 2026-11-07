import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cropRect, isGeometry, streamUrl, type Geometry } from "@/lib/glasshand";

const BACKOFF = [2000, 5000, 15000];
const STALL_MS = 10_000; // nothing drawn for this long (also after opening): back to snapshots and reconnect

/** Live iPhone view: cropped JPEG frames from the relay, falling back to polled snapshots until a frame is drawn. */
export function GlasshandLive({ rentalId }: { rentalId: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const paused = useRef(false);
  const [isPaused, setPaused] = useState(false);
  const [live, setLive] = useState(false); // a frame has been drawn on the current connection
  const [fps, setFps] = useState(0);
  const [snap, setSnap] = useState(() => api.deviceScreenshotUrl());

  useEffect(() => {
    let ws: WebSocket | null = null, timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false, attempt = 0, busy = false, frames = 0, lastDraw = 0;
    let geo: Geometry | null = null, frameId: number | null = null;
    let pending: { data: ArrayBuffer; id: number | null } | null = null;

    const draw = async (data: ArrayBuffer, g: Geometry) => {
      const c = canvas.current, ctx = c?.getContext("2d", { alpha: false });
      if (!c || !ctx) return false;
      const bmp = await createImageBitmap(new Blob([data], { type: "image/jpeg" }));
      try {
        const [vx, vy, vw, vh] = cropRect(g, bmp.width, bmp.height);
        if (c.width !== vw || c.height !== vh) { c.width = vw; c.height = vh; }
        ctx.drawImage(bmp, vx, vy, vw, vh, 0, 0, vw, vh);
        return true;
      } finally { bmp.close(); }
    };
    // Latest frame wins. Each drawn frame is acked, which lets Glasshand send more (at most 4 unacked).
    const pump = async () => {
      if (busy) return;
      busy = true;
      try {
        while (pending && !paused.current && !stopped) {
          const { data, id } = pending, s = ws, g = geo;
          pending = null;
          const ok = !!g && (await draw(data, g).catch(() => false));
          if (!ok || !s || s !== ws) continue;
          frames++; lastDraw = Date.now(); attempt = 0; setLive(true);
          if (id !== null) s.send(JSON.stringify({ type: "frame_ack", frameId: id }));
        }
      } finally { busy = false; }
    };
    const open = () => {
      if (stopped) return;
      const s = new WebSocket(streamUrl());
      ws = s; geo = null; frameId = null; pending = null; lastDraw = Date.now();
      s.binaryType = "arraybuffer";
      s.onmessage = (e) => {
        if (ws !== s) return;
        if (typeof e.data !== "string") { pending = { data: e.data as ArrayBuffer, id: frameId }; frameId = null; void pump(); return; }
        let m: { type?: unknown; geometry?: unknown; frameId?: unknown } | null = null;
        try { m = JSON.parse(e.data); } catch { /* ignore malformed control message */ }
        if (m?.type === "hello") { if (isGeometry(m.geometry)) geo = m.geometry; else s.close(); }
        else if (m?.type === "frame") frameId = Number.isSafeInteger(m.frameId) ? (m.frameId as number) : null;
        else if (m?.type === "error") s.close();
      };
      const fail = () => {
        if (stopped || ws !== s) return;
        ws = null; pending = null; setLive(false); setFps(0);
        timer = setTimeout(open, BACKOFF[Math.min(attempt++, BACKOFF.length - 1)]);
      };
      s.onerror = fail;
      s.onclose = fail;
    };
    const tick = setInterval(() => {
      setFps(frames); frames = 0;
      if (paused.current) lastDraw = Date.now(); // paused is not stalled
      else if (Date.now() - lastDraw > STALL_MS) ws?.close(); // fail() shows snapshots and reconnects
      else void pump(); // draw the frame held while paused
    }, 1000);
    open();
    return () => { stopped = true; clearTimeout(timer); clearInterval(tick); ws?.close(); setLive(false); };
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
          <canvas ref={canvas} aria-label="Live iPhone screen" role="img" className={live ? "size-full object-contain bg-black" : "hidden"} />
          {!live && <img src={snap} alt="iPhone screen snapshot" className="size-full object-contain bg-black" />}
        </div>
      </div>
      {!live && <p role="status" className="text-xs text-muted-foreground">Live stream unavailable — showing snapshots</p>}
    </div>
  );
}

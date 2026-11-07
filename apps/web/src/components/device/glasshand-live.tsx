import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cropRect, feedMode, streamUrl, type FeedMode, type Geometry } from "@/lib/glasshand";

const BACKOFF = [2000, 5000, 15000];
const SNAPSHOT_MS = 1500;

type Why = "socket" | "capture" | "frames";
interface Feed { mode: FeedMode; why: Why; fps: number; received: number; drawn: number }

/**
 * Live iPhone view: cropped JPEG frames from the relay. Polled snapshots show whenever frames are not
 * actually arriving (socket down, no first frame within ~3 s, frames stalled ~5 s, capture unavailable).
 */
export function GlasshandLive({ rentalId }: { rentalId: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const paused = useRef(false);
  const [isPaused, setPaused] = useState(false);
  const [feed, setFeed] = useState<Feed>({ mode: "snapshots", why: "socket", fps: 0, received: 0, drawn: 0 });
  const [snap, setSnap] = useState(() => api.deviceScreenshotUrl());

  useEffect(() => {
    let ws: WebSocket | null = null, timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false, attempt = 0, busy = false, warned = false;
    let frames = 0, received = 0, drawn = 0;
    let geo: Geometry | null = null, helloAt: number | null = null, lastFrameAt: number | null = null, capture = true;

    const tick = setInterval(() => {
      const mode = feedMode({ helloAt, lastFrameAt, captureAvailable: capture, paused: paused.current, now: Date.now() });
      const why: Why = helloAt === null ? "socket" : !capture ? "capture" : "frames";
      setFeed({ mode, why, fps: frames, received, drawn });
      frames = 0;
    }, 1000);

    const draw = async (buf: ArrayBuffer) => {
      const c = canvas.current;
      if (!c || !geo) return;
      busy = true;
      let bmp: ImageBitmap | undefined;
      try {
        bmp = await createImageBitmap(new Blob([buf], { type: "image/jpeg" }));
        const [vx, vy, vw, vh] = cropRect(geo, bmp.width, bmp.height);
        if (c.width !== vw || c.height !== vh) { c.width = vw; c.height = vh; }
        c.getContext("2d")?.drawImage(bmp, vx, vy, vw, vh, 0, 0, c.width, c.height);
        frames++; drawn++; lastFrameAt = Date.now();
      } catch (err) {
        if (!warned) { warned = true; console.warn("Glasshand live frame could not be drawn", err); }
      } finally { bmp?.close(); busy = false; }
    };
    const open = () => {
      if (stopped) return;
      const s = new WebSocket(streamUrl());
      ws = s;
      s.binaryType = "arraybuffer";
      s.onmessage = (e) => {
        if (typeof e.data === "string") {
          try {
            const m = JSON.parse(e.data);
            if (m.type === "hello" && m.geometry?.viewport) { geo = m.geometry; helloAt = Date.now(); attempt = 0; }
            else if (m.type === "capture_status") capture = m.available !== false;
            else if (m.type === "error") s.close();
          } catch { /* ignore malformed control message */ }
        } else if (e.data instanceof ArrayBuffer) {
          received++;
          if (!busy && !paused.current) void draw(e.data);
        }
      };
      const fail = () => {
        if (stopped || ws !== s) return;
        ws = null; geo = null; helloAt = null; lastFrameAt = null; capture = true;
        timer = setTimeout(open, BACKOFF[Math.min(attempt++, BACKOFF.length - 1)]);
      };
      s.onerror = fail;
      s.onclose = fail;
    };
    open();
    return () => { stopped = true; clearTimeout(timer); clearInterval(tick); ws?.close(); };
  }, [rentalId]);

  const live = feed.mode === "live";
  useEffect(() => {
    if (live) return;
    const id = setInterval(() => { if (!document.hidden) setSnap(api.deviceScreenshotUrl()); }, SNAPSHOT_MS);
    return () => clearInterval(id);
  }, [live]);

  const diag = feed.why === "socket" ? undefined : `${feed.received} frames received, ${feed.drawn} drawn`;
  const note = feed.mode !== "snapshots" ? null
    : feed.why === "capture" ? "Screen capture unavailable, showing snapshots"
    : feed.why === "frames" ? "Live stream is not sending frames, showing snapshots"
    : "Live stream unavailable, showing snapshots";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-2">
        {live ? <Badge variant="outline" className="gap-1.5" title={diag}><span className="size-1.5 animate-pulse rounded-full bg-destructive" aria-hidden />LIVE · {isPaused ? "paused" : `${feed.fps} fps`}</Badge>
          : <Badge variant="secondary" title={diag}>{feed.mode === "connecting" ? "CONNECTING" : "SNAPSHOTS"}</Badge>}
        {live && (
          <Button size="sm" variant="ghost" aria-pressed={isPaused} onClick={() => { paused.current = !paused.current; setPaused(paused.current); }}>
            {isPaused ? <Play aria-hidden /> : <Pause aria-hidden />}{isPaused ? "Resume stream" : "Pause stream"}
          </Button>
        )}
      </div>
      <div className="w-full max-w-[220px]">
        <div className="relative aspect-[393/852] overflow-hidden rounded-[3rem] border-[10px] border-neutral-900 bg-neutral-950">
          <div className="absolute left-1/2 top-2 z-10 h-[37px] w-[126px] -translate-x-1/2 rounded-full bg-black" aria-hidden />
          {!live && <img src={snap} alt="iPhone screen snapshot" className="absolute inset-0 size-full object-contain bg-neutral-100" />}
          <canvas ref={canvas} aria-label="Live iPhone screen" role="img" className={live ? "absolute inset-0 size-full object-contain bg-neutral-100" : "hidden"} />
        </div>
      </div>
      {note && <p role="status" className="text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

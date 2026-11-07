import { useEffect, useState } from "react";
import { relativeTime } from "@/lib/time";

export function RelativeTime({ iso, className }: { iso: string; className?: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  return (
    <time dateTime={iso} title={new Date(iso).toLocaleString()} className={className}>
      {relativeTime(iso, now)}
    </time>
  );
}

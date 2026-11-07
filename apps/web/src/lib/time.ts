export const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

const DAY = 86_400_000;

/** Sidebar date buckets, newest first. */
export function dateBucket(iso: string, now = Date.now()): "Today" | "Yesterday" | "Previous 7 days" | "Older" {
  const startOfToday = new Date(now).setHours(0, 0, 0, 0);
  const t = new Date(iso).getTime();
  if (t >= startOfToday) return "Today";
  if (t >= startOfToday - DAY) return "Yesterday";
  if (t >= startOfToday - 7 * DAY) return "Previous 7 days";
  return "Older";
}

export function relativeTime(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

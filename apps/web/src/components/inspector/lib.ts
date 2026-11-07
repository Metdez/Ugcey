// Pure helpers for the inspector (no React, no DOM) so they can be unit tested with `node --test`.
import type { AuditEntry, FileEntry } from "@ugecy/contracts";

export interface FileGroup {
  group: string; // "/research"
  files: { entry: FileEntry; name: string }[]; // name = path relative to the group
}

/** Group virtual-FS files by first path segment. Root-level files go under "/". */
export function groupFiles(files: FileEntry[]): FileGroup[] {
  const map = new Map<string, FileGroup>();
  for (const entry of files) {
    const parts = entry.path.split("/").filter(Boolean);
    const root = parts.length > 1 ? `/${parts[0]}` : "/";
    const name = parts.length > 1 ? parts.slice(1).join("/") : (parts[0] ?? entry.path);
    const g = map.get(root) ?? { group: root, files: [] };
    g.files.push({ entry, name });
    map.set(root, g);
  }
  const groups = [...map.values()].sort((a, b) => a.group.localeCompare(b.group));
  for (const g of groups) g.files.sort((a, b) => a.name.localeCompare(b.name));
  return groups;
}

export type AuditFilter = "all" | AuditEntry["status"];

/** Newest first, optionally restricted to one status. */
export function filterAudit(rows: AuditEntry[], status: AuditFilter): AuditEntry[] {
  return rows
    .filter((r) => status === "all" || r.status === status)
    .sort((a, b) => b.ts.localeCompare(a.ts));
}

export const isDeviceRow = (r: AuditEntry) => !!r.tool?.startsWith("device_");

export function hhmmss(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toTimeString().slice(0, 8);
}

export function duration(startIso: string, endIso?: string, now = Date.now()): string {
  const s = Math.max(0, Math.round(((endIso ? Date.parse(endIso) : now) - Date.parse(startIso)) / 1000));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const s = Math.round((now - Date.parse(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function slugify(s: string): string {
  return s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
}

/** CSS color token for a subagent/agent name (dots, borders, avatars only). */
export function agentColor(name: string): string {
  const key = name.startsWith("research") ? "research"
    : name.startsWith("creative") || name.includes("script") ? "creative"
    : name.startsWith("production") || name.includes("media") ? "production"
    : name.startsWith("publish") ? "publishing"
    : name.startsWith("device") ? "device"
    : name.startsWith("analytic") ? "analytics" : "orchestrator";
  return `var(--agent-${key})`;
}

export const isMarkdown = (path: string) => /\.(md|markdown)$/i.test(path);

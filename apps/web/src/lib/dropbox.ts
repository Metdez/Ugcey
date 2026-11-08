// Typed client for the Worker-handled /api/dropbox/* routes (packages/contracts/INTERNAL-API.md "dropbox.internal").
import type { DropboxStatus } from "@ugecy/contracts";

export type { DropboxStatus };

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!res.ok) {
    const j = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
    throw new Error(j?.error?.code === "invalid_code" ? "That code was not accepted. Open Dropbox again and paste a fresh code." : j?.error?.message ?? `Dropbox request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const dropbox = {
  connect: () => call<{ authorize_url: string }>("POST", "/api/dropbox/connect").then((r) => r.authorize_url),
  submitCode: (code: string) => call<DropboxStatus>("POST", "/api/dropbox/code", { code }),
  status: () => call<DropboxStatus>("GET", "/api/dropbox/status"),
  disconnect: () => call<DropboxStatus>("POST", "/api/dropbox/disconnect"),
  /** Python endpoint: queue every existing asset for copying into Dropbox. */
  backfill: () => call<{ queued: number }>("POST", "/api/storage/backfill"),
};

// Access-key gate: cookie holds sha256(key); /api/* (except /api/edge/*) requires it.
import type { MiddlewareHandler } from "hono";
import type { Env } from "./env";

const COOKIE = "ugecy_key";
const enc = new TextEncoder();

export async function sha256Hex(s: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Constant-time compare via equal-length digests. */
export async function keyMatches(given: string | undefined, expected: string | undefined): Promise<boolean> {
  if (!given || !expected) return false;
  const [a, b] = await Promise.all([sha256Hex(given), sha256Hex(expected)]);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function readCookie(header: string | null, name: string): string | undefined {
  for (const part of (header ?? "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return undefined;
}

export async function cookieValid(header: string | null, accessKey: string | undefined): Promise<boolean> {
  if (!accessKey) return false;
  return keyMatches(readCookie(header, COOKIE), await sha256Hex(accessKey));
}

export async function unlock(c: { req: { query(k: string): string | undefined }; env: Env }): Promise<Response> {
  if (!(await keyMatches(c.req.query("key"), c.env.UGECY_ACCESS_KEY)))
    return new Response("<!doctype html><title>Locked</title><p>Invalid access key.</p>", {
      status: 401,
      headers: { "content-type": "text/html; charset=utf-8" },
    });
  const hash = await sha256Hex(c.env.UGECY_ACCESS_KEY);
  return new Response(null, {
    status: 302,
    headers: {
      location: "/",
      "set-cookie": `${COOKIE}=${hash}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000`,
    },
  });
}

export const requireKey: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  if (c.req.path.startsWith("/api/edge/")) return next();
  if (await cookieValid(c.req.header("cookie") ?? null, c.env.UGECY_ACCESS_KEY)) return next();
  return c.json({ error: { code: "locked", message: "Open the access link to unlock" } }, 401);
};

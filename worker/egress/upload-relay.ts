// hfupload.internal: relays one product-photo upload from the container to Higgsfield's presigned storage URL.
// The container has no internet, and the presigned host is not a credentialed vendor, so it gets its own narrow
// door: PUT only, HTTPS only, Higgsfield's own input bucket only, a signed URL only, a fixed header allowlist, a size
// cap, no redirects, and never any credentials (Higgsfield's docs forbid sending API keys to the presigned URL).
import { errorResponse } from "./llm";

/** Higgsfield's input bucket (observed 2026-11-07). Pinned exactly: S3 bucket names are global and first-come, so a
 *  pattern like fnf-api-input-prod-<digits> could match a bucket someone else registers. If Higgsfield moves buckets,
 *  uploads fail with upload_target_denied and this constant must be updated. */
export const STORAGE_HOST = "fnf-api-input-prod-20250414194641741400000002.s3.amazonaws.com";
const FORWARDED_HEADERS = ["content-type", "x-amz-tagging", "content-length"];
const IGNORED_HEADERS = new Set(["host", "authorization", "cookie", "accept", "accept-encoding", "user-agent", "connection"]);
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** The presigned target from `?to=`, or an error message when it is not an allowed Higgsfield upload URL. */
export function uploadTarget(reqUrl: string): URL | string {
  const raw = new URL(reqUrl).searchParams.get("to");
  if (!raw) return "missing ?to= presigned URL";
  let target: URL;
  try {
    target = new URL(raw);
  } catch {
    return "?to= is not a URL";
  }
  if (target.protocol !== "https:") return "presigned URL must be https";
  if (target.hostname !== STORAGE_HOST) return `host not allowed: ${target.hostname}`;
  if (target.username || target.password || target.port) return "presigned URL must not carry credentials or a port";
  if (!target.searchParams.get("X-Amz-Signature") || !target.searchParams.get("X-Amz-Credential"))
    return "presigned URL must be signed (X-Amz-Signature and X-Amz-Credential)";
  return target;
}

export async function handleUploadRelay(req: Request): Promise<Response> {
  if (req.method !== "PUT") return errorResponse(405, "method_not_allowed", req.method);
  const target = uploadTarget(req.url);
  if (typeof target === "string") return errorResponse(403, "upload_target_denied", target);
  const size = Number(req.headers.get("content-length") ?? "NaN");
  if (!Number.isFinite(size) || size <= 0 || size > MAX_UPLOAD_BYTES)
    return errorResponse(413, "upload_size", "content-length must be between 1 byte and 10 MB");
  const headers = new Headers();
  for (const h of FORWARDED_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  // Higgsfield may add signed upload headers; log their names so a resulting S3 403 is easy to trace.
  const dropped = [...req.headers.keys()].filter((h) => !FORWARDED_HEADERS.includes(h) && !IGNORED_HEADERS.has(h));
  if (dropped.length) console.warn("hfupload relay dropped headers:", dropped.join(", "));
  try {
    const up = await fetch(target.toString(), { method: "PUT", headers, body: req.body, redirect: "manual" });
    return new Response(null, { status: up.status });
  } catch (e) {
    return errorResponse(502, "upstream_error", e instanceof Error ? e.message : String(e));
  }
}

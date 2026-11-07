// hfupload.internal: relays one product-photo upload from the container to Higgsfield's presigned storage URL.
// The container has no internet, and the presigned host is not a credentialed vendor, so it gets its own narrow
// door: PUT only, HTTPS only, Higgsfield's input bucket only, a fixed header allowlist, a size cap, and never any
// credentials (Higgsfield's docs forbid sending API keys to the presigned URL).
import { errorResponse } from "./llm";

/** Higgsfield's input bucket, observed 2026-11-07: fnf-api-input-prod-20250414194641741400000002.s3.amazonaws.com */
const STORAGE_HOST = /^fnf-api-input-prod-\d+\.s3\.amazonaws\.com$/;
const FORWARDED_HEADERS = ["content-type", "x-amz-tagging", "content-length"];
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
  if (!STORAGE_HOST.test(target.hostname)) return `host not allowed: ${target.hostname}`;
  if (target.username || target.password || target.port) return "presigned URL must not carry credentials or a port";
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
  try {
    const up = await fetch(target.toString(), { method: "PUT", headers, body: req.body });
    return new Response(null, { status: up.status });
  } catch (e) {
    return errorResponse(502, "upstream_error", e instanceof Error ? e.message : String(e));
  }
}

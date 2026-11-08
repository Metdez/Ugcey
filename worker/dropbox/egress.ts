// dropbox.internal intercept: local status, allowlisted POST passthrough with token from the DO, one 401 refresh+retry.
import { errorResponse } from "../egress/llm";
import { API, type DropboxRuntime, type FetchFn } from "./types";

const FORWARD = ["content-type", "accept"];
const ALLOWED = new Set([
  "/2/users/get_current_account",
  "/2/files/save_url",
  "/2/files/save_url/check_job_status",
  "/2/files/get_metadata",
  "/2/files/list_folder",
  "/2/files/list_folder/continue",
  "/2/files/get_temporary_link",
  "/2/files/search_v2",
]);
const notConfigured = () => errorResponse(503, "not_configured", "Dropbox is not connected");

export async function handleDropbox(req: Request, rt: DropboxRuntime, f: FetchFn = (i, init) => fetch(i, init)): Promise<Response> {
  const u = new URL(req.url);
  if (u.pathname === "/_ugecy/status" && req.method === "GET") return Response.json(await rt.dropboxStatus());
  if (req.method !== "POST" || !ALLOWED.has(u.pathname)) return errorResponse(403, "path_not_allowed", `${req.method} ${u.pathname}`);

  let token: string | null;
  try {
    token = await rt.dropboxToken();
  } catch {
    return errorResponse(502, "upstream_error", "token refresh failed");
  }
  if (!token) return notConfigured();

  const body = await req.arrayBuffer(); // buffered so a 401 retry can replay it
  const send = (t: string) => {
    const headers = new Headers();
    for (const h of FORWARD) if (req.headers.has(h)) headers.set(h, req.headers.get(h)!);
    headers.set("authorization", `Bearer ${t}`);
    return f(API + u.pathname, { method: "POST", headers, body: body.byteLength ? body : undefined });
  };
  try {
    let r = await send(token);
    if (r.status === 401) {
      await r.body?.cancel();
      const fresh = await rt.dropboxToken(token);
      if (!fresh) return notConfigured();
      r = await send(fresh);
    }
    return r;
  } catch {
    return errorResponse(502, "upstream_error", "dropbox request failed");
  }
}

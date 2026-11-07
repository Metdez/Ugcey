// Pure validation helpers for bindings.internal. No bindings touched here, so they unit-test without a Worker.
export class HttpError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export const errorResponse = (status: number, code: string, message: string): Response =>
  Response.json({ error: { code, message } }, { status });

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const bad = (msg: string): never => {
  throw new HttpError(400, "bad_request", msg);
};

export function obj(v: unknown, what = "body"): Record<string, unknown> {
  return isObj(v) ? v : bad(`${what} must be an object`);
}
export function str(v: unknown, name: string, max = 100_000): string {
  return typeof v === "string" && v.length > 0 && v.length <= max ? v : bad(`${name} must be a non-empty string`);
}
export function params(v: unknown): unknown[] {
  if (v === undefined) return [];
  if (!Array.isArray(v) || v.length > 100) return bad("params must be an array of at most 100 values");
  return v;
}

/** Single statement only; block ATTACH/DETACH/DROP/PRAGMA. The container is trusted code, this is a guard. */
export function guardSql(sql: string): string {
  const s = str(sql, "sql");
  // strip comments and string literals so keywords inside them do not trip the check
  const bare = s
    .replace(/--[^\n]*/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/'(?:[^']|'')*'/g, "''")
    .replace(/"(?:[^"]|"")*"/g, '""')
    .trim()
    .replace(/;\s*$/, "");
  if (bare.includes(";")) bad("only a single SQL statement is allowed");
  if (/\b(attach|detach|drop|pragma)\b/i.test(bare)) bad("ATTACH, DETACH, DROP and PRAGMA are not allowed");
  return s;
}

const PRIVATE_V4 = [/^0\./, /^10\./, /^127\./, /^169\.254\./, /^172\.(1[6-9]|2\d|3[01])\./, /^192\.168\./, /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./, /^22[4-9]\.|^2[3-5]\d\./];

/** http(s) only, no private/loopback/internal hosts. URL() already normalises decimal/hex IPv4 to dotted form. */
export function guardPublicUrl(raw: unknown, name = "url"): URL {
  let u: URL;
  try {
    u = new URL(str(raw, name, 4096));
  } catch (e) {
    if (e instanceof HttpError) throw e;
    return bad(`${name} is not a valid URL`);
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") bad(`${name} must be http(s)`);
  const h = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  const v6 = h.includes(":");
  const blockedName = h === "localhost" || /\.(localhost|local|internal|lan|home\.arpa)$/.test(h) || !h.includes(".") && !v6;
  const blockedV4 = PRIVATE_V4.some((r) => r.test(h));
  const blockedV6 = v6 && (h === "::1" || h === "::" || /^(fc|fd|fe[89ab])/.test(h) || h.startsWith("::ffff:"));
  if (blockedName || blockedV4 || blockedV6) throw new HttpError(400, "forbidden_host", "private or internal hosts are not allowed");
  return u;
}

export const truncate = (s: string, n: number): string => (s.length > n ? s.slice(0, n) : s);

export function titleFromMarkdown(md: string, fallback: string): string {
  return /^#{1,2}\s+(.+)$/m.exec(md)?.[1].trim().slice(0, 300) ?? fallback;
}

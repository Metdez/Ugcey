// usage: D1_ID=.. KV_ID=.. node render-config.mjs <in.jsonc> <out.json>
// Strips JSONC comments/trailing commas, fills the D1/KV ids from env, writes plain JSON (valid jsonc).
import { readFileSync, writeFileSync } from "node:fs";

const [src, dst] = process.argv.slice(2);
const { D1_ID, KV_ID } = process.env;
if (!src || !dst || !D1_ID || !KV_ID) {
  console.error("usage: D1_ID=.. KV_ID=.. node render-config.mjs <in> <out>");
  process.exit(1);
}
// string-aware comment strip: strings are matched first and kept as-is
const text = readFileSync(src, "utf8")
  .replace(/"(?:\\.|[^"\\])*"|\/\/[^\n]*|\/\*[\s\S]*?\*\//g, (m) => (m.startsWith('"') ? m : ""))
  .replace(/,(\s*[}\]])/g, "$1");
const cfg = JSON.parse(text);
for (const d of cfg.d1_databases ?? []) d.database_id = D1_ID;
for (const k of cfg.kv_namespaces ?? []) k.id = KV_ID;
writeFileSync(dst, JSON.stringify(cfg, null, 2));

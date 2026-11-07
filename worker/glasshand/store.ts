// GlasshandStore implementations: DO SQLite (`glasshand` table) and an in-memory one for tests.
import type { GlasshandStore } from "./types";

export function sqlStore(storage: DurableObjectStorage): GlasshandStore {
  const sql = storage.sql;
  sql.exec("CREATE TABLE IF NOT EXISTS glasshand (k TEXT PRIMARY KEY, v TEXT)");
  return {
    all() {
      const out: Record<string, string> = {};
      for (const r of sql.exec<{ k: string; v: string }>("SELECT k, v FROM glasshand")) out[r.k] = r.v;
      return out;
    },
    put(patch) {
      storage.transactionSync(() => {
        for (const [k, v] of Object.entries(patch))
          sql.exec("INSERT INTO glasshand (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", k, v);
      });
    },
    del(keys) {
      storage.transactionSync(() => {
        for (const k of keys) sql.exec("DELETE FROM glasshand WHERE k = ?", k);
      });
    },
  };
}

export function memoryStore(): GlasshandStore {
  const m = new Map<string, string>();
  return {
    all: () => Object.fromEntries(m),
    put: (p) => void Object.entries(p).forEach(([k, v]) => m.set(k, v)),
    del: (ks) => void ks.forEach((k) => m.delete(k)),
  };
}

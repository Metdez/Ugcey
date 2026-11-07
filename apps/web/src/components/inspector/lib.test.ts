/// <reference types="node" />
// Run: node --test --experimental-strip-types src/components/inspector/lib.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { filterAudit, groupFiles } from "./lib.ts";

const f = (path: string) => ({ path, size: 1, modified_at: null });
const a = (id: string, ts: string, status: "ok" | "error") => ({
  id, ts, thread_id: null, actor: "agent" as const, agent: null, action: "tool_call", tool: null, status, mode: "mock" as const, detail: "",
});

test("groupFiles groups by first segment and sorts", () => {
  const g = groupFiles([f("/scripts/b.md"), f("/research/x/y.md"), f("/manifest.json"), f("/scripts/a.md")]);
  assert.deepEqual(g.map((x) => x.group), ["/", "/research", "/scripts"]);
  assert.deepEqual(g[2].files.map((x) => x.name), ["a.md", "b.md"]);
  assert.equal(g[1].files[0].name, "x/y.md");
});

test("filterAudit filters by status, newest first", () => {
  const rows = [a("1", "2026-01-01T00:00:01Z", "ok"), a("2", "2026-01-01T00:00:03Z", "error"), a("3", "2026-01-01T00:00:02Z", "ok")];
  assert.deepEqual(filterAudit(rows, "all").map((r) => r.id), ["2", "3", "1"]);
  assert.deepEqual(filterAudit(rows, "ok").map((r) => r.id), ["3", "1"]);
});

import { expect, test } from "vitest";
import { filterAudit, groupFiles } from "./lib";

const f = (path: string) => ({ path, size: 1, modified_at: null });
const a = (id: string, ts: string, status: "ok" | "error") => ({
  id, ts, thread_id: null, actor: "agent" as const, agent: null, action: "tool_call", tool: null, status, mode: "mock" as const, detail: "",
});

test("groupFiles groups by first segment and sorts", () => {
  const g = groupFiles([f("/scripts/b.md"), f("/research/x/y.md"), f("/manifest.json"), f("/scripts/a.md")]);
  expect(g.map((x) => x.group)).toEqual(["/", "/research", "/scripts"]);
  expect(g[2].files.map((x) => x.name)).toEqual(["a.md", "b.md"]);
  expect(g[1].files[0].name).toBe("x/y.md");
});

test("filterAudit filters by status, newest first", () => {
  const rows = [a("1", "2026-01-01T00:00:01Z", "ok"), a("2", "2026-01-01T00:00:03Z", "error"), a("3", "2026-01-01T00:00:02Z", "ok")];
  expect(filterAudit(rows, "all").map((r) => r.id)).toEqual(["2", "3", "1"]);
  expect(filterAudit(rows, "ok").map((r) => r.id)).toEqual(["3", "1"]);
});

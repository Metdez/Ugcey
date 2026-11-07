import { describe, expect, it } from "vitest";
import type { ApprovalRequest } from "@/types/agent";
import { allowedDecisions, approveAll, editDecisions, rejectAll } from "./approval-decisions";

const req = (allowed: ApprovalRequest["allowed_decisions"] = ["approve", "edit", "reject"]): ApprovalRequest => ({
  tool: "publish_post", agent: "publishing", description: "d", allowed_decisions: allowed,
  args: { caption: "hi", count: 2, paid: false, tags: ["a"] },
});

describe("approval decisions", () => {
  it("one decision per request, in order", () => {
    expect(approveAll(2)).toEqual([{ type: "approve" }, { type: "approve" }]);
    expect(rejectAll(2, " off-brand ")).toEqual([{ type: "reject", message: "off-brand" }, { type: "reject", message: "off-brand" }]);
    expect(rejectAll(1, "")[0]).toEqual({ type: "reject", message: undefined });
  });
  it("intersects allowed decisions", () => {
    expect(allowedDecisions([req(), req(["approve", "reject"])])).toEqual(["approve", "reject"]);
  });
  it("types edited args and validates JSON", () => {
    const ok = editDecisions([req()], [{ caption: "yo", count: "5", paid: true, tags: '["b"]' }]);
    expect(ok).toEqual({ decisions: [{ type: "edit", args: { caption: "yo", count: 5, paid: true, tags: ["b"] } }] });
    const bad = editDecisions([req()], [{ count: "x", tags: "[" }]);
    expect("errors" in bad && Object.keys(bad.errors)).toEqual(["0.count", "0.tags"]);
  });
});

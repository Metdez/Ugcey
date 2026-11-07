import { describe, expect, it } from "vitest";
import type { ApprovalRequest } from "@/types/agent";
import { allowedDecisions, approveAll, costLabel, editDecisions, rejectAll, requestSummary } from "./approval-decisions";

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

describe("approval summary", () => {
  const media = (args: Record<string, unknown>): ApprovalRequest => ({
    tool: "generate_media", agent: "production-coordinator", allowed_decisions: ["approve", "edit", "reject"],
    description: "Tool execution requires approval Tool: generate_media Args: {...}", args,
  });
  it("names stills and clips in plain words", () => {
    expect(requestSummary(media({ model: "marketing-studio/image/flare", kind: "image", prompt: "p", args: { resolution: "2k" } })))
      .toEqual({ title: "Generate an image (Marketing Studio Flare, 2k)", prompt: "p" });
    expect(requestSummary(media({ model: "bytedance/seedance-2.5/image-to-video", prompt: "q", args: { duration: 15, resolution: "480p" } })).title)
      .toBe("Generate a 15 s video (Seedance 2.5, 480p)");
  });
  it("labels cost", () => {
    expect(costLabel(0.0512)).toBe("About $0.05");
    expect(costLabel(null)).toBe("Price unknown");
    expect(costLabel(0.006)).toBe("Under $0.01");
  });
});

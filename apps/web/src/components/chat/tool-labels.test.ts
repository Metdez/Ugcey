import { describe, expect, it } from "vitest";
import { agentColor, toolFilePath, toolLabel } from "./tool-labels";

describe("toolLabel", () => {
  it("carries state in the sentence", () => {
    expect(toolLabel("web_search", { query: "ugc hooks" }, "running")).toBe("Searching the web for ugc hooks…");
    expect(toolLabel("write_file", { file_path: "/research/x.md" }, "complete")).toBe("Wrote /research/x.md");
    expect(toolLabel("generate_media", {}, "error")).toBe("Failed to generate media");
    expect(toolLabel("custom_tool", {}, "running")).toBe("Running custom_tool…");
  });
  it("extracts file paths and agent colours", () => {
    expect(toolFilePath({ file_path: "/a.md" })).toBe("/a.md");
    expect(toolFilePath({ file_path: "a.md" })).toBeNull();
    expect(agentColor("research-analyst")).toBe("var(--agent-research)");
    expect(agentColor("ugecy")).toBe("var(--agent-orchestrator)");
  });
});

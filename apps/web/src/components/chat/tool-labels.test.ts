import { describe, expect, it } from "vitest";
import { agentColor, toolFilePath, toolLabel } from "./tool-labels";

describe("toolLabel", () => {
  it("carries state in the sentence", () => {
    expect(toolLabel("web_search", { query: "ugc hooks" }, "running")).toBe("Searching the web for ugc hooks…");
    expect(toolLabel("write_file", { file_path: "/research/x.md" }, "complete")).toBe("Wrote /research/x.md");
    expect(toolLabel("generate_media", {}, "error")).toBe("Failed to generate media");
    expect(toolLabel("custom_tool", {}, "running")).toBe("Running custom_tool…");
    expect(toolLabel("deep_search", { query: "hooks" }, "complete")).toBe("Searched the web in depth for hooks");
    expect(toolLabel("read_pages", { urls: ["https://a", "https://b"] }, "running")).toBe("Reading 2 pages…");
    expect(toolLabel("deep_research", { question: "winning hooks" }, "error")).toBe("Research failed for winning hooks");
    expect(toolLabel("fetch_page", { url: "https://a.com" }, "complete")).toBe("Fetched https://a.com");
  });
  it("extracts file paths and agent colours", () => {
    expect(toolFilePath({ file_path: "/a.md" })).toBe("/a.md");
    expect(toolFilePath({ file_path: "a.md" })).toBeNull();
    expect(agentColor("research-analyst")).toBe("var(--agent-research)");
    expect(agentColor("ugecy")).toBe("var(--agent-orchestrator)");
  });
});

import { stripJson } from "./trace/subagent-line";
it("stripJson hides echoed screen JSON but keeps prose", () => {
  expect(stripJson('{"app": "Home", "elements": [{"label": "A {b}", "x": 0.1}]}I see the dialog. Tapping "Not Now".'))
    .toBe('I see the dialog. Tapping "Not Now".');
});

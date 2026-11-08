import { describe, expect, it } from "vitest";
import { notConnected } from "./not-connected";

describe("notConnected", () => {
  it("lists only capabilities that are off", () => {
    const r = notConnected({ llm: "live", media: "off", device: "live", publishing: "off", research: "off", tavily: "off", storage: "live" });
    expect(r.map((x) => x.key)).toEqual(["media", "research", "tavily", "publishing"]);
    expect(r[0].text).toContain("HF_KEY");
    expect(r[1].text).toContain("FIRECRAWL_API_KEY");
    expect(r[2].text).toContain("TAVILY_API_KEY");
  });
  it("is empty when everything is live and offers Device tab for device", () => {
    expect(notConnected({ llm: "live", media: "live", device: "live", publishing: "live", research: "live", tavily: "live", storage: "live" })).toEqual([]);
    expect(notConnected({ llm: "live", media: "live", device: "off", publishing: "live", research: "live", tavily: "live", storage: "live" })[0].action).toBe("device");
  });
});

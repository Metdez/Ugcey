import { describe, expect, it } from "vitest";
import { notConnected } from "./not-connected";

describe("notConnected", () => {
  it("lists only capabilities that are off", () => {
    const r = notConnected({ llm: "live", media: "off", device: "live", publishing: "off", research: "off", storage: "live" });
    expect(r.map((x) => x.key)).toEqual(["media", "research", "publishing"]);
    expect(r[0].text).toContain("HF_KEY");
  });
  it("is empty when everything is live and offers Device tab for device", () => {
    expect(notConnected({ llm: "live", media: "live", device: "live", publishing: "live", research: "live", storage: "live" })).toEqual([]);
    expect(notConnected({ llm: "live", media: "live", device: "off", publishing: "live", research: "live", storage: "live" })[0].action).toBe("device");
  });
});

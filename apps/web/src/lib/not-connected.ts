import type { ProviderModes } from "@ugecy/contracts";

export interface NotConnected { key: keyof ProviderModes; text: string; action?: "device" }

const MESSAGES: Partial<Record<keyof ProviderModes, Omit<NotConnected, "key">>> = {
  media: { text: "Higgsfield not connected — add the HF_KEY Worker secret" },
  device: { text: "iPhone not connected — Connect Glasshand", action: "device" },
  research: { text: "Live web search not connected — add FIRECRAWL_API_KEY (phone research still works)" },
  publishing: { text: "Direct publishing not connected — posts go through the iPhone with approval" },
};

/** Capabilities whose mode is "off", with how to connect each. */
export const notConnected = (modes: ProviderModes): NotConnected[] =>
  (Object.keys(MESSAGES) as (keyof ProviderModes)[]).filter((k) => modes[k] === "off").map((k) => ({ key: k, ...MESSAGES[k]! }));

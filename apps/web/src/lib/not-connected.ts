import type { ProviderModes } from "@ugecy/contracts";

export interface NotConnected { key: keyof ProviderModes; text: string; action?: "device" }

const MESSAGES: Partial<Record<keyof ProviderModes, Omit<NotConnected, "key">>> = {
  media: { text: "Higgsfield not connected — add the HF_KEY Worker secret" },
  device: { text: "iPhone not connected — Connect Glasshand", action: "device" },
  research: { text: "Web research (Firecrawl) not connected — add the FIRECRAWL_API_KEY Worker secret" },
  tavily: { text: "Deep research (Tavily) not connected — add the TAVILY_API_KEY Worker secret" },
  publishing: { text: "Publishing not connected — connect the Glasshand iPhone (posts go through the phone with approval)" },
  storage: { text: "Dropbox is not connected. Connect it from Accounts in the sidebar." },
};

/** Capabilities whose mode is "off", with how to connect each. */
export const notConnected = (modes: ProviderModes): NotConnected[] =>
  (Object.keys(MESSAGES) as (keyof ProviderModes)[]).filter((k) => modes[k] === "off").map((k) => ({ key: k, ...MESSAGES[k]! }));

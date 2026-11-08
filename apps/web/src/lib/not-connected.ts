import type { ProviderModes } from "@ugecy/contracts";

export interface NotConnected { key: keyof ProviderModes; text: string; action?: "device" }

const MESSAGES: Partial<Record<keyof ProviderModes, Omit<NotConnected, "key">>> = {
  media: { text: "Video generation not connected — add its API key secret (README, Secrets)" },
  device: { text: "iPhone not connected — connect it in the Device tab", action: "device" },
  research: { text: "Web research not connected — add its API key secret (README, Secrets)" },
  tavily: { text: "Deep research not connected — add its API key secret (README, Secrets)" },
  publishing: { text: "Publishing not connected — connect the iPhone (posts go through the phone with approval)" },
  storage: { text: "Dropbox is not connected. Connect it from Accounts in the sidebar." },
};

/** Capabilities whose mode is "off", with how to connect each. */
export const notConnected = (modes: ProviderModes): NotConnected[] =>
  (Object.keys(MESSAGES) as (keyof ProviderModes)[]).filter((k) => modes[k] === "off").map((k) => ({ key: k, ...MESSAGES[k]! }));

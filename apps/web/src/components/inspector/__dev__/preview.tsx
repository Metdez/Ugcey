// Dev-only: open /src/components/inspector/__dev__/preview.html?tab=<tab> with `pnpm --filter web dev`.
import { createRoot } from "react-dom/client";
import "@/index.css";
import { useThreadStore } from "@/stores/thread-store";
import { emptySnapshot, type InspectorTab } from "@/types/agent";
import { InspectorTabContent, TAB_ORDER } from "..";
import * as fx from "../__fixtures__";

const routes: Record<string, unknown> = {
  "/api/config": fx.config, "/api/memories": fx.memories, "/api/assets": fx.assetsRemote,
  "/api/approvals": fx.approvalHistory, "/api/audit": fx.audit, "/api/device": fx.device,
  "/api/threads/t1/files": { path: "/research/hook-patterns.md", content: "# Hook patterns\n\n- Problem-first opener\n- Before/after reveal\n\n| hook | uses |\n|---|---|\n| stop doing this | 8 |" },
};
const realFetch = window.fetch;
window.fetch = (input, init) => {
  const path = new URL(String(input instanceof Request ? input.url : input), location.origin).pathname;
  if (path in routes) return Promise.resolve(new Response(JSON.stringify(routes[path]), { headers: { "content-type": "application/json" } }));
  if (path === "/api/device/screenshot") return Promise.resolve(new Response("", { status: 404 }));
  return realFetch(input, init);
};

useThreadStore.setState({ ...emptySnapshot(), ...fx.thread });
const tab = (new URLSearchParams(location.search).get("tab") ?? "plan") as InspectorTab;
createRoot(document.getElementById("root")!).render(
  <div className="mx-auto min-h-svh w-[380px] border-x bg-background text-foreground" data-tabs={TAB_ORDER.join()}>
    <InspectorTabContent tab={tab} />
  </div>,
);

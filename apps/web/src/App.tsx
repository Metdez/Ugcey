import { useEffect } from "react";
import { AssetLightbox, ChatView } from "@/components/chat";
import { AppShell } from "@/components/shell/app-shell";
import { Toaster } from "@/components/ui/sonner";
import { useThreadRoute } from "@/hooks/use-thread-route";
import { useWorkspace } from "@/stores/workspace-store";

export default function App() {
  useEffect(() => { void useWorkspace.getState().boot(); }, []);
  useThreadRoute();
  return (
    <>
      <AppShell><ChatView /></AppShell>
      <AssetLightbox />
      <Toaster theme="dark" />
    </>
  );
}

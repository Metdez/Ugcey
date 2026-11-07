import { useEffect } from "react";
import { useThreadStore } from "@/stores/thread-store";
import { fixtureSnapshot } from "../__fixtures__/snapshot";
import { ChatView } from "../chat-view";
import { AssetLightbox } from "../../assets/asset-lightbox";

/** Dev-only: mount with `?preview=chat` (WP-A's main.tsx may lazy-import this under import.meta.env.DEV). */
export default function ChatPreview() {
  useEffect(() => { useThreadStore.setState(fixtureSnapshot); }, []);
  return (
    <div className="h-screen bg-background text-foreground">
      <ChatView />
      <AssetLightbox />
    </div>
  );
}

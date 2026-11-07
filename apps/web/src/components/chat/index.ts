// WP-B public entry point (FROZEN export names). WP-B replaces these stubs with real components.
// WP-A imports ChatView; WP-C imports ApprovalCard, AssetThumb, AssetLightbox.
import { createElement } from "react";

export function ChatView() {
  return createElement("div", { className: "p-6 text-muted-foreground" }, "Chat (WP-B)");
}

export function ApprovalCard(props: { approvalId: string; variant: "inline" | "panel" }) {
  return createElement("div", null, `Approval ${props.approvalId}`);
}

export function AssetThumb(props: { assetId: string; size?: "sm" | "md" | "lg" }) {
  return createElement("div", null, `Asset ${props.assetId}`);
}

/** Mount once (WP-A mounts it in AppShell); reads useUi().lightboxAssetId. */
export function AssetLightbox() {
  return null;
}

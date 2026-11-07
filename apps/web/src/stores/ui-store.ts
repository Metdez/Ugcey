// UI store (FROZEN API; WP-A may extend fields but not rename). Inspector focus + panes + dialogs.
import { create } from "zustand";
import type { InspectorTab } from "@/types/agent";

export type FocusKind = "file" | "source" | "asset" | "approval" | "subagent" | "audit" | "memory";

interface UiState {
  inspectorOpen: boolean;
  inspectorTab: InspectorTab;
  focus: { kind: FocusKind; id: string } | null;
  paletteOpen: boolean;
  shortcutsOpen: boolean;
  lightboxAssetId: string | null;
  lastViewed: Partial<Record<InspectorTab, number>>;
  openInspector: (tab: InspectorTab, focus?: { kind: FocusKind; id: string }) => void;
  toggleInspector: () => void;
  setTab: (tab: InspectorTab) => void;
  openLightbox: (assetId: string | null) => void;
  setPalette: (open: boolean) => void;
  setShortcuts: (open: boolean) => void;
}

export const useUi = create<UiState>((set) => ({
  inspectorOpen: true,
  inspectorTab: "plan",
  focus: null,
  paletteOpen: false,
  shortcutsOpen: false,
  lightboxAssetId: null,
  lastViewed: {},
  openInspector: (tab, focus) =>
    set((s) => ({ inspectorOpen: true, inspectorTab: tab, focus: focus ?? null,
      lastViewed: { ...s.lastViewed, [tab]: Date.now() } })),
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
  setTab: (tab) => set((s) => ({ inspectorTab: tab, focus: null, lastViewed: { ...s.lastViewed, [tab]: Date.now() } })),
  openLightbox: (assetId) => set({ lightboxAssetId: assetId }),
  setPalette: (open) => set({ paletteOpen: open }),
  setShortcuts: (open) => set({ shortcutsOpen: open }),
}));

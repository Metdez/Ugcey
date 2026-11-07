// Tiny URL sync: the open thread lives in `?t=<id>`; other params are kept.
export const getThreadParam = () => new URLSearchParams(location.search).get("t");

export function setThreadParam(id: string | null, mode: "push" | "replace" = "push") {
  const u = new URL(location.href);
  if (id) u.searchParams.set("t", id);
  else u.searchParams.delete("t");
  if (u.href === location.href) return;
  history[mode === "push" ? "pushState" : "replaceState"](null, "", u);
}

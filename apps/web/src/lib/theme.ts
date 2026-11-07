// Dark by default (index.html has class="dark"); preference kept in localStorage.
export type Theme = "dark" | "light";

export function getTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function setTheme(t: Theme) {
  document.documentElement.classList.toggle("dark", t === "dark");
  try { localStorage.setItem("ugecy.theme", t); } catch { /* private mode */ }
}

export function initTheme() {
  try { if (localStorage.getItem("ugecy.theme") === "light") setTheme("light"); } catch { /* ignore */ }
}

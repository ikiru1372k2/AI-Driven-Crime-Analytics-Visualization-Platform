/**
 * App theme (light / dark). Dark is the CSS default; setting
 * `data-theme="light"` on <html> switches every token. The choice persists in
 * localStorage and falls back to the OS preference on first visit.
 */
export type Theme = "dark" | "light";

const KEY = "kavach-theme";

export function initialTheme(): Theme {
  const saved = localStorage.getItem(KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  localStorage.setItem(KEY, t);
}

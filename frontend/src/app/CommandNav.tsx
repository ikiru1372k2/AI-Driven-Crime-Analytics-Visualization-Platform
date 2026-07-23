/**
 * Command shell navigation (design review 1f) — the full 9-module
 * DETECT→EXPLAIN story is visible even where modules are roadmap:
 * shipped modules navigate, roadmap modules render as "soon" (honest,
 * not hidden). Scope is pinned so users always know their clearance
 * context (STATE seam until CAT-003/#19 binds real roles).
 */
export type ModuleView =
  | "overview"
  | "map"
  | "graph"
  | "identities"
  | "evidence"
  | "mo"
  | "anomalies"
  | "forecast";

interface NavItem {
  label: string;
  view?: ModuleView;
  soon?: boolean;
  badge?: string;
  dot: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

interface Props {
  view: ModuleView;
  onView: (v: ModuleView) => void;
  alertCount: number;
  identityCount: number;
  flagCount: number;
  theme: string;
  onToggleTheme: () => void;
}

export function CommandNav({
  view,
  onView,
  alertCount,
  identityCount,
  flagCount,
  theme,
  onToggleTheme,
}: Props) {
  const groups: NavGroup[] = [
    {
      label: "DETECT",
      items: [
        { label: "Geospatial Ops", view: "map", dot: "#3987e5" },
        {
          label: "Trends",
          view: "overview",
          dot: "#3987e5",
          badge: alertCount > 0 ? String(alertCount) : undefined,
        },
      ],
    },
    { label: "UNDERSTAND", items: [{ label: "MO Profiles", view: "mo", dot: "#d9a13b" }] },
    {
      label: "CONNECT",
      items: [
        { label: "Networks", view: "graph", dot: "#a76fb9" },
        {
          label: "Identities",
          view: "identities",
          dot: "#a76fb9",
          badge: identityCount > 0 ? String(identityCount) : undefined,
        },
      ],
    },
    {
      label: "FLAG",
      items: [
        {
          label: "Anomalies",
          view: "anomalies",
          dot: "#d95926",
          badge: flagCount > 0 ? String(flagCount) : undefined,
        },
      ],
    },
    { label: "FORECAST", items: [{ label: "Area Risk", view: "forecast", dot: "#5aa9a3" }] },
    { label: "EXPLAIN", items: [{ label: "Evidence", view: "evidence", dot: "#3c9a5f" }] },
  ];

  return (
    <nav className="cmdnav" aria-label="Modules">
      <button
        className={"tab-brand cmd-home" + (view === "overview" ? " active" : "")}
        onClick={() => onView("overview")}
        title="KAVACH Command — state intelligence overview"
      >
        KAVACH AI
      </button>

      <div className="cmd-groups">
        {groups.map((g) => (
          <div key={g.label} className="cmd-group">
            <span className="cmd-group-label">{g.label}</span>
            <div className="cmd-items">
              {g.items.map((it) =>
                it.soon ? (
                  <span key={it.label} className="cmd-item soon" title="Roadmap module">
                    <span className="cmd-dot" style={{ background: it.dot }} aria-hidden />
                    {it.label}
                    <span className="soon-tag">soon</span>
                  </span>
                ) : (
                  <button
                    key={it.label}
                    className={"cmd-item" + (view === it.view ? " active" : "")}
                    onClick={() => onView(it.view!)}
                  >
                    <span className="cmd-dot" style={{ background: it.dot }} aria-hidden />
                    {it.label}
                    {it.badge && <span className="cmd-badge">{it.badge}</span>}
                  </button>
                ),
              )}
            </div>
          </div>
        ))}
      </div>

      <span className="scope-chip" title="Authorization scope (CAT-003/#19 binds real roles)">
        STATE · Karnataka
      </span>
      <button
        className="theme-toggle"
        onClick={onToggleTheme}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      >
        {theme === "dark" ? "☀" : "☾"}
      </button>
    </nav>
  );
}

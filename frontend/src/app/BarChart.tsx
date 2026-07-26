/**
 * Minimal horizontal bar chart — no dependency, matches the app's SVG chart
 * style (see Sparkline.tsx). Used for district/age-band distributions.
 */
interface Row {
  label: string;
  value: number;
}

interface Props {
  rows: Row[];
  color?: string;
  height?: number;
  formatValue?: (v: number) => string;
}

export function BarChart({ rows, color = "#3987e5", height = 22, formatValue }: Props) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="bar-chart" role="img" aria-label="Bar chart">
      {rows.map((r) => (
        <div className="bar-chart-row" key={r.label}>
          <span className="bar-chart-label" title={r.label}>
            {r.label}
          </span>
          <div className="bar-chart-track" style={{ height }}>
            <div
              className="bar-chart-fill"
              style={{ width: `${(r.value / max) * 100}%`, background: color }}
            />
          </div>
          <span className="bar-chart-value">{formatValue ? formatValue(r.value) : r.value}</span>
        </div>
      ))}
      {rows.length === 0 && <p className="muted small">No data.</p>}
    </div>
  );
}
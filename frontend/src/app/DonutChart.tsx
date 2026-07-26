/**
 * Minimal SVG donut chart — no dependency. Used for status / crime-category
 * breakdowns. Renders a legend beside the ring; slices carry a title tooltip.
 */
interface Slice {
  label: string;
  value: number;
  color: string;
}

interface Props {
  slices: Slice[];
  size?: number;
  thickness?: number;
}

export function DonutChart({ slices, size = 140, thickness = 22 }: Props) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;

  let offset = 0;
  const arcs = slices.map((s) => {
    const frac = s.value / total;
    const dash = frac * circumference;
    const arc = (
      <circle
        key={s.label}
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={s.color}
        strokeWidth={thickness}
        strokeDasharray={`${dash} ${circumference - dash}`}
        strokeDashoffset={-offset}
        transform={`rotate(-90 ${cx} ${cy})`}
      >
        <title>{`${s.label}: ${s.value} (${Math.round(frac * 100)}%)`}</title>
      </circle>
    );
    offset += dash;
    return arc;
  });

  return (
    <div className="donut-chart">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Donut chart">
        {slices.length === 0 ? (
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="#3a3a38" strokeWidth={thickness} />
        ) : (
          arcs
        )}
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central" className="donut-total">
          {total}
        </text>
      </svg>
      <ul className="donut-legend">
        {slices.map((s) => (
          <li key={s.label}>
            <span className="donut-swatch" style={{ background: s.color }} aria-hidden />
            {s.label} <b>{s.value}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
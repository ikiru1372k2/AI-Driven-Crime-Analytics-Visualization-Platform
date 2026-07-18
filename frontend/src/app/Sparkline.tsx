/**
 * Compact weekly-count sparkline for a trend alert. Baseline weeks render in a
 * recessive blue, the recent (scored) weeks in the alert's severity color, and
 * a dashed line marks the robust baseline median — so the deviation the engine
 * flagged is visible at a glance.
 */
interface Props {
  series: number[]; // oldest -> newest
  recentWeeks: number;
  baselineMedian: number;
  color: string; // severity color for the recent bars
  width?: number;
  height?: number;
}

export function Sparkline({
  series,
  recentWeeks,
  baselineMedian,
  color,
  width = 168,
  height = 46,
}: Props) {
  const max = Math.max(1, ...series);
  const n = series.length;
  const gap = 2;
  const bw = (width - gap * (n - 1)) / n;
  const recentStart = n - recentWeeks;
  const baseY = height - (baselineMedian / max) * height;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Weekly counts, baseline median ${baselineMedian}`}
    >
      {series.map((v, i) => {
        const h = Math.max(1, (v / max) * height);
        const isRecent = i >= recentStart;
        return (
          <rect
            key={i}
            x={i * (bw + gap)}
            y={height - h}
            width={bw}
            height={h}
            rx={1.5}
            fill={isRecent ? color : "#3987e5"}
            opacity={isRecent ? 1 : 0.5}
          >
            <title>{`week ${i - n + 1 === 0 ? "0" : i - n + 1}: ${v} case${v === 1 ? "" : "s"}`}</title>
          </rect>
        );
      })}
      {/* robust baseline median */}
      <line
        x1={0}
        x2={width}
        y1={baseY}
        y2={baseY}
        stroke="#c3c2b7"
        strokeWidth={1}
        strokeDasharray="3 3"
        opacity={0.7}
      />
    </svg>
  );
}

import { useMemo } from "react";

export type SparklinePoint = {
  value: number;
  label?: string;
};

export type SparklineProps = {
  points: SparklinePoint[];
  width?: number;
  height?: number;
  stroke?: string;
  /** Optional [min, max] band shaded behind the line for "target range". */
  band?: [number, number];
  bandColor?: string;
  /** Format the value for the tooltip / endpoint label. */
  formatValue?: (value: number) => string;
  ariaLabel?: string;
};

/**
 * Tiny dependency-free SVG line chart. Used on the Analytics page for trend
 * strips. No external chart library to keep the bundle lean.
 *
 * - Auto-scales to the data unless a `band` is provided, in which case the
 *   y-axis is clamped to include the band.
 * - Renders nothing meaningful (just an empty axis) when there are <2 points.
 */
export default function Sparkline({
  points,
  width = 220,
  height = 60,
  stroke = "var(--neon-cyan, #28f4ff)",
  band,
  bandColor = "rgba(125, 255, 138, 0.18)",
  formatValue = (v) => v.toFixed(2),
  ariaLabel
}: SparklineProps) {
  const { path, dots, last, minY, maxY } = useMemo(() => {
    if (points.length === 0) {
      return { path: "", dots: [] as Array<{ x: number; y: number; p: SparklinePoint }>, last: null, minY: 0, maxY: 1 };
    }
    const values = points.map((p) => p.value);
    let minV = Math.min(...values);
    let maxV = Math.max(...values);
    if (band) {
      minV = Math.min(minV, band[0]);
      maxV = Math.max(maxV, band[1]);
    }
    if (minV === maxV) {
      // Pad so a flat line doesn't collapse to the bottom edge.
      minV -= 0.5;
      maxV += 0.5;
    }
    const pad = 6;
    const innerW = Math.max(1, width - pad * 2);
    const innerH = Math.max(1, height - pad * 2);
    const xStep = points.length > 1 ? innerW / (points.length - 1) : 0;
    const toY = (v: number) => pad + innerH - ((v - minV) / (maxV - minV)) * innerH;

    const dotsArr = points.map((p, i) => ({
      x: pad + xStep * i,
      y: toY(p.value),
      p
    }));
    const pathStr = dotsArr
      .map((d, i) => `${i === 0 ? "M" : "L"}${d.x.toFixed(2)},${d.y.toFixed(2)}`)
      .join(" ");
    return {
      path: pathStr,
      dots: dotsArr,
      last: dotsArr[dotsArr.length - 1],
      minY: minV,
      maxY: maxV
    };
  }, [points, band, width, height]);

  if (points.length === 0) {
    return (
      <svg width={width} height={height} role="img" aria-label={ariaLabel ?? "no data"}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(255,255,255,0.02)" rx="6" />
        <text x={width / 2} y={height / 2} textAnchor="middle" fill="rgba(183, 198, 218, 0.7)" fontSize="11">
          no data
        </text>
      </svg>
    );
  }

  const pad = 6;
  const innerH = Math.max(1, height - pad * 2);
  let bandRect: JSX.Element | null = null;
  if (band) {
    const [bMin, bMax] = band;
    const top = pad + innerH - ((bMax - minY) / (maxY - minY)) * innerH;
    const bottom = pad + innerH - ((bMin - minY) / (maxY - minY)) * innerH;
    bandRect = (
      <rect
        x={pad}
        y={top}
        width={width - pad * 2}
        height={Math.max(0, bottom - top)}
        fill={bandColor}
        rx="4"
      />
    );
  }

  return (
    <svg width={width} height={height} role="img" aria-label={ariaLabel}>
      {bandRect}
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {dots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r={1.5} fill={stroke}>
          <title>
            {d.p.label ? `${d.p.label}: ` : ""}
            {formatValue(d.p.value)}
          </title>
        </circle>
      ))}
      {last && (
        <text
          x={Math.min(width - 4, last.x + 6)}
          y={Math.max(10, last.y)}
          fontSize="10"
          fill="rgba(231, 240, 255, 0.85)"
          textAnchor="end"
        >
          {formatValue(last.p.value)}
        </text>
      )}
    </svg>
  );
}

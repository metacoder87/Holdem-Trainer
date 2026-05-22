import type { BayesianStat } from "../api/client";

/**
 * Display a poker rate stat with its Bayesian credible interval.
 *
 * Why this exists: showing "VPIP 29%" hides whether that's a real
 * leak or 12 hands of noise. Showing "VPIP 29% (CI 21-37%, n=87)"
 * makes the user immediately see whether the number is trustworthy
 * AND whether it's actually outside the target band.
 *
 * Props:
 *  - ``label``  -- "VPIP" / "PFR" / etc.
 *  - ``stat``   -- BayesianStat from backend (value + CI + sample).
 *  - ``format`` -- "percent" multiplies by 100 + appends "%";
 *                  "ratio" prints with 2 decimals (for AGG factor).
 *  - ``optimal`` -- optional "expected" or "target" value shown
 *                   alongside as a faint reference number.
 */
type Props = {
  label: string;
  stat: BayesianStat | undefined | null;
  format?: "percent" | "ratio";
  optimal?: number | string;
};

function fmt(value: number, mode: "percent" | "ratio") {
  if (mode === "percent") return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(2);
}

function flagFromPosition(pos: "low" | "high" | null | undefined): {
  text: string;
  tone: "good" | "warn" | "bad";
} {
  if (pos === "high") return { text: "Above target", tone: "warn" };
  if (pos === "low") return { text: "Below target", tone: "warn" };
  return { text: "In range", tone: "good" };
}

export default function BayesianStatCard({
  label,
  stat,
  format = "percent",
  optimal,
}: Props) {
  if (!stat) {
    return (
      <div className="stat-card bayes-card">
        <div className="stat-label">{label}</div>
        <div className="stat-value">—</div>
        <div className="stat-delta">No data yet</div>
      </div>
    );
  }

  const point = fmt(stat.value, format);
  const lo = fmt(stat.ci_lower, format);
  const hi = fmt(stat.ci_upper, format);

  const flag = flagFromPosition(stat.position_vs_target);
  const sampleNote = stat.small_sample
    ? `n=${stat.sample_size} (small sample)`
    : `n=${stat.sample_size}`;

  return (
    <div className="stat-card bayes-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${flag.tone}`}>{point}</div>
      <div className="stat-delta">
        <span title={`95% credible interval`}>
          CI {lo} – {hi}
        </span>
      </div>
      <div className={`stat-sub ${stat.small_sample ? "warn" : ""}`}>
        {sampleNote}
      </div>
      {stat.position_vs_target !== undefined &&
        stat.target_low !== undefined &&
        stat.target_high !== undefined && (
          <div className={`stat-flag ${flag.tone}`}>
            {flag.text} ({fmt(stat.target_low, format)}–
            {fmt(stat.target_high, format)})
          </div>
        )}
      {optimal !== undefined && (
        <div className="stat-sub muted">target ≈ {optimal}</div>
      )}
    </div>
  );
}

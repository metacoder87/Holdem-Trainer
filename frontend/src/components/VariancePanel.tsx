import { useEffect, useState, lazy, Suspense } from "react";
import type { VarianceReport } from "../api/client";
import { getVarianceReport } from "../api/client";

const StatsChart = lazy(() => import("./StatsChart"));

/**
 * Variance + risk-of-ruin + all-in luck panel.
 *
 * Renders four key quant numbers:
 *  - Winrate BB/100 with 95% CI
 *  - Std-dev (variance per session)
 *  - Risk of ruin (when a bankroll is entered)
 *  - Kelly fraction (when bankroll given)
 *
 * Plus the realized vs EV-adjusted cumulative graph (the classic
 * "luck-adjusted winrate" line poker pros all use). The user can
 * type their bankroll (in BBs) to enable RoR + Kelly; we don't
 * persist it - it's a what-if input.
 */
type Props = {
  player: string | undefined;
};

function fmtBB100(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)} BB/100`;
}

function fmtRoR(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtKelly(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  // Kelly is expressed as a fraction of bankroll to risk per hand.
  // The decimal is too small to read; multiply by 100 BB so we
  // render "X BB per shot" instead.
  return `${(v * 100).toFixed(3)} per 100 BB`;
}

export default function VariancePanel({ player }: Props) {
  const [report, setReport] = useState<VarianceReport | null>(null);
  const [bankrollBbs, setBankrollBbs] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!player) {
      setReport(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getVarianceReport(player, bankrollBbs > 0 ? bankrollBbs : undefined)
      .then((data) => {
        if (cancelled) return;
        setReport(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load variance");
        setReport(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [player, bankrollBbs]);

  const wr = report?.winrate;
  const luck = report?.all_in_luck;

  // Build chart data from the ev_adjusted_lines payload.
  const chartData = (report?.ev_adjusted_lines || []).map((row) => ({
    label: row.label,
    value: row.realized,
    realized_cumulative_bb: row.realized,
    ev_cumulative_bb: row.ev,
  }));

  return (
    <div className="panel variance-panel">
      <div className="panel-header">
        <h2>Variance &amp; Risk</h2>
        <p>
          Skill-vs-luck decomposition, bankroll risk, and Kelly sizing. Enter
          your bankroll in BBs to see risk-of-ruin and Kelly fraction.
        </p>
      </div>

      <div className="variance-bankroll-input">
        <label htmlFor="variance-bankroll" className="muted">
          Bankroll (in BBs)
        </label>
        <input
          id="variance-bankroll"
          type="number"
          min={0}
          step={50}
          value={bankrollBbs || ""}
          onChange={(e) => setBankrollBbs(Number(e.target.value) || 0)}
          placeholder="e.g. 2000"
        />
      </div>

      {loading && <div className="muted">Loading…</div>}
      {error && <div className="warn">{error}</div>}

      {report && (
        <>
          <div className="variance-grid">
            <div className="stat-card">
              <div className="stat-label">Winrate</div>
              <div
                className={`stat-value ${
                  (wr?.mean_bb100 ?? 0) >= 0 ? "good" : "warn"
                }`}
              >
                {fmtBB100(wr?.mean_bb100)}
              </div>
              <div className="stat-delta">
                CI {fmtBB100(wr?.ci_lower)} – {fmtBB100(wr?.ci_upper)}
              </div>
              <div className="stat-sub muted">
                {wr?.total_hands ?? 0} hands across {wr?.session_count ?? 0}{" "}
                sessions
                {wr?.small_sample && " (small sample)"}
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Std deviation</div>
              <div className="stat-value">
                {wr ? `${wr.std_bb100.toFixed(1)} BB/100` : "—"}
              </div>
              <div className="stat-delta muted">per-session σ</div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Risk of ruin</div>
              <div
                className={`stat-value ${
                  wr?.risk_of_ruin !== null &&
                  wr?.risk_of_ruin !== undefined &&
                  wr.risk_of_ruin > 0.1
                    ? "warn"
                    : ""
                }`}
              >
                {fmtRoR(wr?.risk_of_ruin)}
              </div>
              <div className="stat-delta muted">
                {bankrollBbs > 0
                  ? `at ${bankrollBbs} BB bankroll`
                  : "enter bankroll above"}
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Kelly fraction</div>
              <div className="stat-value">{fmtKelly(wr?.kelly_fraction)}</div>
              <div className="stat-delta muted">
                growth-optimal stake size
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">All-in luck</div>
              <div
                className={`stat-value ${
                  (luck?.luck_bb_total ?? 0) > 0 ? "good" : "warn"
                }`}
              >
                {luck ? fmtBB100(luck.luck_bb_total) : "—"}
              </div>
              <div className="stat-delta muted">
                {luck
                  ? `${luck.sessions_with_data} sessions w/ priced decisions`
                  : "no priced decisions logged yet"}
              </div>
            </div>
          </div>

          {chartData.length > 0 && (
            <div className="variance-chart">
              <div className="muted small">
                Realized vs all-in EV-adjusted cumulative winnings (BB).
                The gap between the two lines is "luck".
              </div>
              <Suspense fallback={<div className="muted">Loading chart…</div>}>
                <StatsChart
                  data={chartData}
                  label="Cumulative BB"
                  height={260}
                  showEvAdjusted
                />
              </Suspense>
            </div>
          )}
        </>
      )}
    </div>
  );
}

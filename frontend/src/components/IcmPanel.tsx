import { useMemo, useState } from "react";
import type { IcmReport } from "../api/client";
import { getIcmForSpot } from "../api/client";

/**
 * ICM equity calculator panel for tournament situations.
 *
 * The user enters a tournament spot (per-seat stacks + payout
 * schedule) and we render:
 *  - Each seat's $ equity vs chip-share baseline (the ICM gap).
 *  - Hero's risk premium for an all-in coinflip — how much equity
 *    edge you need over 50% before chip-EV gambles become ICM-EV
 *    positive. This is the single most important number in late-
 *    tournament play.
 *
 * The default scenario is a final-table-bubble preset so the panel
 * has meaningful content even before the user types anything.
 */
type Props = {
  player: string | undefined;
};

const DEFAULT_STACKS = "5000, 5000, 100";
const DEFAULT_PAYOUTS = "600, 400";

function parseList(input: string): number[] {
  return input
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n >= 0);
}

function fmtDollar(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `$${v.toFixed(2)}`;
}

function fmtPercent(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

export default function IcmPanel({ player: _player }: Props) {
  const [stacksInput, setStacksInput] = useState(DEFAULT_STACKS);
  const [payoutsInput, setPayoutsInput] = useState(DEFAULT_PAYOUTS);
  const [heroIndex, setHeroIndex] = useState(0);
  const [report, setReport] = useState<IcmReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const stacks = useMemo(() => parseList(stacksInput), [stacksInput]);
  const payouts = useMemo(() => parseList(payoutsInput), [payoutsInput]);

  const canCompute =
    stacks.length >= 2 &&
    stacks.length <= 9 &&
    payouts.length >= 1 &&
    payouts.length <= stacks.length &&
    heroIndex >= 0 &&
    heroIndex < stacks.length;

  const compute = async () => {
    if (!canCompute) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getIcmForSpot({
        stacks,
        payouts,
        hero_index: heroIndex,
      });
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compute ICM");
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel icm-panel">
      <div className="panel-header">
        <h2>ICM equity (tournament)</h2>
        <p>
          Malmuth-Harville model. Chip leaders are under-paid in $ terms;
          short stacks over-paid. Risk premium tells you how big your edge
          must be before an all-in is ICM-profitable.
        </p>
      </div>

      <div className="icm-controls">
        <label>
          <span className="muted small">Stacks (chips, comma-separated)</span>
          <input
            type="text"
            value={stacksInput}
            onChange={(e) => setStacksInput(e.target.value)}
            placeholder="5000, 3000, 2000"
          />
        </label>
        <label>
          <span className="muted small">Payouts ($, descending)</span>
          <input
            type="text"
            value={payoutsInput}
            onChange={(e) => setPayoutsInput(e.target.value)}
            placeholder="500, 300, 200"
          />
        </label>
        <label>
          <span className="muted small">Hero seat (0-based)</span>
          <input
            type="number"
            min={0}
            max={Math.max(0, stacks.length - 1)}
            value={heroIndex}
            onChange={(e) => setHeroIndex(Number(e.target.value) || 0)}
          />
        </label>
        <button
          type="button"
          className="btn primary"
          onClick={compute}
          disabled={!canCompute || loading}
        >
          {loading ? "Computing…" : "Calculate ICM"}
        </button>
      </div>

      {error && <div className="warn">{error}</div>}

      {report?.icm && (
        <>
          <div className="icm-grid">
            <div className="stat-card">
              <div className="stat-label">Total prize</div>
              <div className="stat-value">
                {fmtDollar(report.icm.total_prize)}
              </div>
              <div className="stat-delta muted">
                {report.icm.total_chips.toLocaleString()} chips in play
              </div>
            </div>
            {report.risk_premium && (
              <>
                <div className="stat-card">
                  <div className="stat-label">Hero ICM equity</div>
                  <div className="stat-value good">
                    {fmtDollar(report.risk_premium.hero_icm_equity_now)}
                  </div>
                  <div className="stat-delta muted">
                    chip-share baseline:{" "}
                    {fmtDollar(
                      report.icm.chip_shares[report.hero_index ?? 0]
                    )}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Risk premium</div>
                  <div
                    className={`stat-value ${
                      report.risk_premium.risk_premium > 0.02 ? "warn" : ""
                    }`}
                  >
                    {fmtPercent(report.risk_premium.risk_premium)}
                  </div>
                  <div className="stat-delta muted">
                    extra equity needed vs chip-EV breakeven
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Bubble factor</div>
                  <div
                    className={`stat-value ${
                      report.risk_premium.bubble_factor > 1.3
                        ? "warn"
                        : ""
                    }`}
                  >
                    {report.risk_premium.bubble_factor.toFixed(2)}
                  </div>
                  <div className="stat-delta muted">
                    $-loss / $-gain on a 50/50 jam
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="icm-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Seat</th>
                  <th>Stack</th>
                  <th>Chip share ($)</th>
                  <th>ICM equity ($)</th>
                  <th>ICM gap</th>
                </tr>
              </thead>
              <tbody>
                {report.icm.equities.map((eq, idx) => {
                  const chipShare = report.icm!.chip_shares[idx];
                  const gap = eq - chipShare;
                  const gapText = gap >= 0 ? `+${gap.toFixed(2)}` : gap.toFixed(2);
                  return (
                    <tr
                      key={idx}
                      className={
                        idx === (report.hero_index ?? 0) ? "row-hero" : ""
                      }
                    >
                      <td>
                        {idx}
                        {idx === (report.hero_index ?? 0) ? " (hero)" : ""}
                      </td>
                      <td>{stacks[idx]?.toLocaleString()}</td>
                      <td>{fmtDollar(chipShare)}</td>
                      <td>{fmtDollar(eq)}</td>
                      <td className={gap >= 0 ? "good" : "warn"}>{gapText}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {report && !report.icm && report.note && (
        <div className="muted">{report.note}</div>
      )}
    </div>
  );
}

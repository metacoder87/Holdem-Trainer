import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import Sparkline from "../components/Sparkline";
import {
  getAnalyticsLeaks,
  getAnalyticsSummary,
  getCareer,
  getEvSummary,
  type AnalyticsSummary,
  type CareerResponse,
  type EvSummaryResponse,
  type LeaksResponse
} from "../api/client";

// Optimal target bands per metric. Sourced from `OPTIMAL` in
// backend/app/services/summary_service.py so the chart's shaded reference
// region matches the leak-detection thresholds.
const METRIC_BANDS: Record<string, [number, number]> = {
  vpip: [0.20, 0.28],
  pfr: [0.15, 0.22],
  aggression_factor: [2.0, 3.5]
};

const SEVERITY_TONE: Record<string, string> = {
  high: "bad",
  medium: "warn",
  low: "good"
};

function formatPct(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(0)}%`;
}

function formatFloat(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return value.toFixed(2);
}

export default function Analytics() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [leaks, setLeaks] = useState<LeaksResponse | null>(null);
  const [career, setCareer] = useState<CareerResponse | null>(null);
  const [ev, setEv] = useState<EvSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setError(null);

    Promise.all([
      getAnalyticsSummary(activePlayer || undefined),
      getAnalyticsLeaks(activePlayer || undefined),
      getCareer(activePlayer || undefined),
      getEvSummary(activePlayer || undefined)
    ])
      .then(([summaryRes, leaksRes, careerRes, evRes]) => {
        if (!active) return;
        setAnalytics(summaryRes);
        setLeaks(leaksRes);
        setCareer(careerRes);
        setEv(evRes);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load analytics");
      });

    return () => {
      active = false;
    };
  }, [activePlayer]);

  const metrics = analytics?.metrics ?? {};
  const trends = analytics?.trends ?? {};
  const sessionCount = analytics?.session_count ?? 0;

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Analytics</h2>
          <p>
            {sessionCount > 0
              ? `Across ${sessionCount} session${sessionCount === 1 ? "" : "s"} for ${
                  analytics?.player?.name ?? activePlayer ?? "this player"
                }.`
              : "Play a session to populate trends and leaks."}
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-card">
            <div className="stat-label">VPIP</div>
            <div className="stat-value">{formatPct(metrics.vpip)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">PFR</div>
            <div className="stat-value">{formatPct(metrics.pfr)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">AGG</div>
            <div className="stat-value">{formatFloat(metrics.aggression_factor)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">DEC</div>
            <div className="stat-value">{formatPct(metrics.decision_accuracy)}</div>
          </div>
        </div>
        {error && <div className="form-status">{error}</div>}
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Trend Overview</h2>
            <p>Last {Math.max(...Object.values(trends).map((t) => t.length), 0)} sessions. Shaded band = optimal range.</p>
          </div>
          <div style={{ display: "grid", gap: 12 }}>
            {Object.entries(trends).map(([metric, points]) => {
              if (points.length === 0) return null;
              const isPct = metric !== "aggression_factor" && metric !== "profit";
              const formatter = (v: number) => (isPct ? `${(v * 100).toFixed(0)}%` : v.toFixed(2));
              return (
                <div key={metric} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div className="stat-label" style={{ minWidth: 70 }}>
                    {metric.toUpperCase()}
                  </div>
                  <Sparkline
                    points={points.map((p) => ({
                      value: p.value,
                      label: p.started_at
                    }))}
                    band={METRIC_BANDS[metric]}
                    formatValue={formatter}
                    ariaLabel={`${metric} trend over recent sessions`}
                  />
                  <div className="timeline-detail" style={{ marginLeft: "auto" }}>
                    {points.length} pt
                  </div>
                </div>
              );
            })}
            {Object.values(trends).every((t) => t.length === 0) && (
              <div className="timeline-item">
                <div className="timeline-body">
                  <div className="timeline-label">No trend data</div>
                  <div className="timeline-detail">Play a session to start tracking.</div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Leak Radar</h2>
            <p>Auto-detected leaks ranked by severity.</p>
          </div>
          {leaks && leaks.leaks.length > 0 ? (
            <ul className="focus-list">
              {leaks.leaks.map((leak) => (
                <li key={leak.id}>
                  <span className={`stat-delta ${SEVERITY_TONE[leak.severity] ?? "warn"}`}>
                    [{leak.severity.toUpperCase()}]
                  </span>{" "}
                  {leak.title}
                  {leak.fix && <div className="timeline-detail">{leak.fix}</div>}
                </li>
              ))}
            </ul>
          ) : (
            <div className="timeline-item">
              <div className="timeline-body">
                <div className="timeline-label">No leaks detected</div>
                <div className="timeline-detail">
                  {sessionCount > 0
                    ? "You're inside the optimal ranges for tracked metrics."
                    : "Play a session to detect leaks."}
                </div>
              </div>
            </div>
          )}
          {summary?.focus_queue?.length > 0 && (
            <div className="panel-header" style={{ marginTop: 16 }}>
              <h3>Focus Queue</h3>
              <p>Pulled from your latest dashboard summary.</p>
            </div>
          )}
          {summary?.focus_queue?.length > 0 && (
            <ul className="focus-list">
              {summary.focus_queue.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {ev && ev.ev.graded_decisions > 0 && (
        <section className="section">
          <div className="section-header">
            <h2>EV Grading</h2>
            <p>
              Chip-denominated cost of every postflop facing-bet decision against
              your equity. Smaller is better (zero means you always took the EV-max line).
            </p>
          </div>
          <div className="hero-stats">
            <div className="stat-card">
              <div className="stat-label">EV bled (BB)</div>
              <div className={`stat-value ${ev.ev.total_bb < -2 ? "warn" : "good"}`}>
                {ev.ev.total_bb.toFixed(1)} BB
              </div>
              <div className="stat-delta">{ev.ev.graded_decisions} graded</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">EV bled (chips)</div>
              <div className={`stat-value ${ev.ev.total_chips < 0 ? "warn" : "good"}`}>
                ${ev.ev.total_chips.toFixed(0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg / decision</div>
              <div className="stat-value">
                {(ev.ev.avg_loss_bb_per_decision || 0).toFixed(3)} BB
              </div>
            </div>
          </div>
          {ev.ev.top_leaks.length > 0 && (
            <div className="panel" style={{ marginTop: 12 }}>
              <div className="panel-header">
                <h3>Biggest individual leaks</h3>
                <p>Top {ev.ev.top_leaks.length} costliest decisions in your last 200 hands.</p>
              </div>
              <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", opacity: 0.75 }}>
                    <th>Hand</th>
                    <th>Street</th>
                    <th>Action</th>
                    <th>EV loss</th>
                    <th>Equity vs. need</th>
                  </tr>
                </thead>
                <tbody>
                  {ev.ev.top_leaks.map((leak, i) => (
                    <tr key={`${leak.hand_number}-${i}`}>
                      <td>
                        {leak.hand_number ? (
                          <Link to={`/replay/${leak.hand_number}`}>#{leak.hand_number}</Link>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>{leak.betting_round}</td>
                      <td>{leak.chosen_action}</td>
                      <td className="warn">
                        {leak.ev_loss_bb.toFixed(2)} BB ({leak.ev_loss_chips.toFixed(0)})
                      </td>
                      <td>
                        {typeof leak.equity === "number"
                          ? `${(leak.equity * 100).toFixed(0)}%`
                          : "?"}
                        {" vs "}
                        {typeof leak.required_equity === "number"
                          ? `${(leak.required_equity * 100).toFixed(0)}%`
                          : "?"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {career?.career_metrics && career.career_metrics.total_sessions > 0 && (
        <section className="section">
          <div className="section-header">
            <h2>Career</h2>
            <p>
              Long-term aggregates across {career.career_metrics.total_sessions} session
              {career.career_metrics.total_sessions === 1 ? "" : "s"} and{" "}
              {career.career_metrics.total_hands.toLocaleString()} hands.
            </p>
          </div>
          <div className="hero-stats">
            <div className="stat-card">
              <div className="stat-label">Total Hands</div>
              <div className="stat-value">{career.career_metrics.total_hands.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Profit</div>
              <div className={`stat-value ${career.career_metrics.total_profit >= 0 ? "good" : "warn"}`}>
                ${career.career_metrics.total_profit.toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Best Session</div>
              <div className="stat-value good">${career.career_metrics.best_session_profit.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Worst Session</div>
              <div className="stat-value warn">${career.career_metrics.worst_session_profit.toLocaleString()}</div>
            </div>
          </div>
          {career.milestones.length > 0 && (
            <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-header">
                <h3>Milestones</h3>
              </div>
              <ul className="focus-list">
                {career.milestones.slice(-5).reverse().map((milestone) => (
                  <li key={milestone.achieved_at + milestone.type}>
                    <strong>{milestone.type.replace(/_/g, " ")}</strong>{" "}
                    <span className="timeline-detail">
                      ({milestone.total_hands.toLocaleString()} hands)
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </>
  );
}

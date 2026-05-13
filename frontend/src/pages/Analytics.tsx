import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  getAnalyticsReport,
  getAnalyticsSessions,
  getChartData,
  getPlayers,
  type AnalyticsReport,
  type JsonValue,
  type PlayerSummary
} from "../api/client";

const StatsChart = lazy(() => import("../components/StatsChart"));

type ChartPoint = {
  label: string;
  value: number;
};

const defaultMetrics: Record<string, string> = {
  vpip: "VPIP",
  pfr: "PFR",
  aggression_factor: "Aggression",
  decision_accuracy: "Decision Accuracy",
  quiz_accuracy: "Quiz Accuracy",
  profit: "Profit",
  hands_played: "Hands Played"
};

function formatValue(value: JsonValue | undefined) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  }
  if (value === null || value === undefined) return "-";
  return String(value);
}

export default function Analytics() {
  const { summary, activePlayer, setActivePlayer } = useOutletContext<ShellContext>();
  const player = activePlayer || summary.player.name || "Guest";
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [metric, setMetric] = useState("vpip");
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [sessions, setSessions] = useState<Array<Record<string, JsonValue>>>([]);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getPlayers()
      .then(setPlayers)
      .catch(() => setPlayers([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getChartData(metric, player),
      getAnalyticsReport(player),
      getAnalyticsSessions(player, 10)
    ])
      .then(([history, nextReport, nextSessions]) => {
        if (cancelled) return;
        setChartData(history);
        setReport(nextReport);
        setSessions(nextSessions);
        setStatus(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setChartData([]);
        setReport(null);
        setSessions([]);
        setStatus(err instanceof Error ? err.message : "Failed to fetch analytics.");
      });
    return () => {
      cancelled = true;
    };
  }, [metric, player]);

  const metricOptions = useMemo(() => report?.metric_options ?? defaultMetrics, [report]);

  return (
    <>
      <section className="section">
        <div className="section-header">
          <div>
            <h2>Analytics</h2>
            <p>Session trends, leaks, and training signals from recorded play.</p>
          </div>
          <div className="toolbar-row">
            <label className="inline-select">
              Profile
              <select value={player} onChange={(event) => setActivePlayer?.(event.target.value)}>
                <option value={player}>{player}</option>
                {players
                  .filter((item) => item.name !== player)
                  .map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
            <label className="inline-select">
              Metric
              <select value={metric} onChange={(event) => setMetric(event.target.value)}>
                {Object.entries(metricOptions).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {status && <div className="form-status">{status}</div>}
        <div className="hero-stats">
          {summary.live_metrics.map((item) => (
            <div key={item.label} className="stat-card">
              <div className="stat-label">{item.label}</div>
              <div className={`stat-value ${item.tone}`}>{item.value}</div>
              <div className={`stat-delta ${item.tone}`}>{item.delta}</div>
            </div>
          ))}
          <div className="stat-card">
            <div className="stat-label">Strategy Score</div>
            <div className="stat-value">{report?.strategy_score ?? "-"}</div>
          </div>
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Trend Overview</h2>
            <p>{metricOptions[metric] ?? metric}</p>
          </div>
          <div className="chart-container" style={{ minHeight: 300 }}>
            {chartData.length > 0 ? (
              <Suspense fallback={<div className="chart-placeholder"><div className="chart-label">Loading chart...</div></div>}>
                <StatsChart data={chartData} label={metricOptions[metric] ?? metric} />
              </Suspense>
            ) : (
              <div className="chart-placeholder">
                <div className="chart-grid" />
                <div className="chart-label">Play tracked sessions to populate trends</div>
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Leak Radar</h2>
            <p>Detected profile: {report?.playing_style.player_type || "Unknown"}</p>
          </div>
          {report ? (
            <ul className="focus-list">
              {report.recommendations.map((rec, i) => (
                <li key={`${rec}-${i}`}>{rec}</li>
              ))}
              {report.recommendations.length === 0 && (
                <li className="text-slate-500">No major leaks detected from recorded sessions.</li>
              )}
            </ul>
          ) : (
            <div className="p-4 text-slate-400">No analytics report available.</div>
          )}
        </div>
      </section>

      <section className="section">
        <div className="panel">
          <div className="panel-header">
            <h2>Recent Sessions</h2>
            <p>Rows come from the same analytics source used by charts and reports.</p>
          </div>
          <div className="session-table">
            <div className="session-table-row header">
              <span>Mode</span>
              <span>Hands</span>
              <span>Profit</span>
              <span>Decision</span>
              <span>Quiz</span>
            </div>
            {sessions.map((session, index) => (
              <div className="session-table-row" key={String(session.id ?? index)}>
                <span>{formatValue(session.game_type)}</span>
                <span>{formatValue(session.hands_played)}</span>
                <span>{formatValue(session.profit ?? session.net_result)}</span>
                <span>{typeof session.decision_accuracy === "number" ? `${Math.round(session.decision_accuracy * 100)}%` : "-"}</span>
                <span>{typeof session.quiz_accuracy === "number" ? `${Math.round(session.quiz_accuracy * 100)}%` : "-"}</span>
              </div>
            ))}
            {sessions.length === 0 && (
              <div className="session-table-row">
                <span>No sessions recorded for this profile.</span>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}

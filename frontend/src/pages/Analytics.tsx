import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import BayesianStatCard from "../components/BayesianStatCard";
import VariancePanel from "../components/VariancePanel";
import IcmPanel from "../components/IcmPanel";
import RegretHeatmap from "../components/RegretHeatmap";
import RangeEquityPanel from "../components/RangeEquityPanel";
import {
  getAnalyticsReport,
  getAnalyticsSessions,
  getChartData,
  getEvLeakReport,
  getPlayers,
  type AnalyticsReport,
  type ChartRow,
  type EvLeakReport,
  type JsonValue,
  type Metric,
  type PlayerSummary
} from "../api/client";

const StatsChart = lazy(() => import("../components/StatsChart"));

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

function formatBb(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)} bb`;
}

type MetricCardDefinition = {
  key: string;
  label: string;
  percent?: boolean;
  low?: number;
  high?: number;
};

const metricCardDefinitions: MetricCardDefinition[] = [
  { key: "vpip", label: "VPIP", percent: true, low: 0.2, high: 0.28 },
  { key: "pfr", label: "PFR", percent: true, low: 0.15, high: 0.22 },
  { key: "aggression_factor", label: "AGG", low: 2.0, high: 3.5 },
  { key: "decision_accuracy", label: "DEC", percent: true, low: 0.65, high: 1 }
];

function numberValue(value: JsonValue | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function sessionWeight(session: Record<string, JsonValue>) {
  const hands = numberValue(session.hands_played);
  return hands && hands > 0 ? hands : 0;
}

function weightedMetric(sessions: Array<Record<string, JsonValue>>, key: string) {
  let totalWeight = 0;
  let weighted = 0;
  for (const session of sessions) {
    const value = numberValue(session[key]);
    const weight = sessionWeight(session);
    if (value === null || weight <= 0) continue;
    totalWeight += weight;
    weighted += value * weight;
  }
  return totalWeight > 0 ? weighted / totalWeight : null;
}

function latestMetricValues(sessions: Array<Record<string, JsonValue>>, key: string) {
  const values: number[] = [];
  for (const session of sessions) {
    const value = numberValue(session[key]);
    if (value !== null) values.push(value);
  }
  return {
    latest: values.length ? values[values.length - 1] : 0,
    previous: values.length >= 2 ? values[values.length - 2] : 0
  };
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatPercentDelta(value: number, previous: number) {
  const diff = Math.round((value - previous) * 100);
  return `${diff >= 0 ? "+" : ""}${diff}%`;
}

function formatFloatDelta(value: number, previous: number) {
  const diff = value - previous;
  return `${diff >= 0 ? "+" : ""}${diff.toFixed(1)}`;
}

function metricTone(definition: MetricCardDefinition, value: number): Metric["tone"] {
  if (definition.low !== undefined && definition.high !== undefined) {
    return value >= definition.low && value <= definition.high ? "good" : "warn";
  }
  return "warn";
}

function analyticsMetricCards(
  sessions: Array<Record<string, JsonValue>>,
  fallback: Metric[]
): Metric[] {
  if (sessions.length === 0) return fallback;
  const hasWeightedData = metricCardDefinitions.some((definition) => (
    weightedMetric(sessions, definition.key) !== null
  ));
  if (!hasWeightedData) return fallback;

  return metricCardDefinitions.map((definition) => {
    const average = weightedMetric(sessions, definition.key) ?? 0;
    const { latest, previous } = latestMetricValues(sessions, definition.key);
    return {
      label: definition.label,
      value: definition.percent ? formatPercent(average) : average.toFixed(1),
      delta: definition.percent
        ? formatPercentDelta(latest, previous)
        : formatFloatDelta(latest, previous),
      tone: metricTone(definition, average)
    };
  });
}

export default function Analytics() {
  const { summary, activePlayer, setActivePlayer } = useOutletContext<ShellContext>();
  const player = activePlayer || summary.player.name || "Guest";
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [metric, setMetric] = useState("vpip");
  // Rolling-window size for the trend chart. Window=1 disables it.
  const [rollingWindow, setRollingWindow] = useState(1);
  // Whether to overlay the EV-adjusted cumulative line (profit metric).
  const [showAdjusted, setShowAdjusted] = useState(false);
  const [chartData, setChartData] = useState<ChartRow[]>([]);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [evReport, setEvReport] = useState<EvLeakReport | null>(null);
  const [sessions, setSessions] = useState<Array<Record<string, JsonValue>>>([]);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getPlayers()
      .then(setPlayers)
      .catch(() => setPlayers([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus(null);
    Promise.allSettled([
      getChartData(metric, player, {
        window: rollingWindow,
        includeAdjusted: showAdjusted,
      }),
      getAnalyticsReport(player),
      getAnalyticsSessions(player, 10),
      getEvLeakReport(player, 20)
    ])
      .then(([historyResult, reportResult, sessionsResult, evResult]) => {
        if (cancelled) return;
        setChartData(historyResult.status === "fulfilled" ? historyResult.value : []);
        setReport(reportResult.status === "fulfilled" ? reportResult.value : null);
        setSessions(sessionsResult.status === "fulfilled" ? sessionsResult.value : []);
        setEvReport(evResult.status === "fulfilled" ? evResult.value : null);
        const failures = [historyResult, reportResult, sessionsResult, evResult].filter(
          (result) => result.status === "rejected"
        );
        if (failures.length === 4) {
          const reason = failures[0].reason;
          setStatus(reason instanceof Error ? reason.message : "Failed to fetch analytics.");
        } else {
          setStatus(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [metric, player, rollingWindow, showAdjusted]);

  const metricOptions = useMemo(() => report?.metric_options ?? defaultMetrics, [report]);
  const metricCards = useMemo(
    () => analyticsMetricCards(sessions, summary.live_metrics),
    [sessions, summary.live_metrics]
  );

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
          {/*
            Bayesian-first row: each rate stat carries a credible
            interval and small-sample warning. Legacy bare-number
            fallbacks shown below for any metric that doesn't yet
            have CI data (e.g. decision accuracy).
          */}
          <BayesianStatCard
            label="VPIP"
            stat={report?.playing_style.vpip_ci}
            format="percent"
            optimal="20-28%"
          />
          <BayesianStatCard
            label="PFR"
            stat={report?.playing_style.pfr_ci}
            format="percent"
            optimal="15-22%"
          />
          <BayesianStatCard
            label="Aggression"
            stat={report?.playing_style.aggression_factor_ci}
            format="ratio"
            optimal="2.0-3.5"
          />
          {/*
            Decision accuracy isn't a Bayesian stat in the backend
            yet; keep the legacy card for it so the row still has
            four equal cells visually.
          */}
          {metricCards
            .filter((item) => item.label === "DEC")
            .map((item) => (
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
            <div className="chart-toolbar">
              <label className="inline-select">
                Rolling window
                <select
                  value={rollingWindow}
                  onChange={(e) => setRollingWindow(Number(e.target.value))}
                >
                  <option value={1}>off</option>
                  <option value={3}>3 sessions</option>
                  <option value={5}>5 sessions</option>
                  <option value={10}>10 sessions</option>
                </select>
              </label>
              {metric === "profit" && (
                <label className="inline-select">
                  <input
                    type="checkbox"
                    checked={showAdjusted}
                    onChange={(e) => setShowAdjusted(e.target.checked)}
                  />{" "}
                  Show EV-adjusted line
                </label>
              )}
            </div>
          </div>
          <div className="chart-container" style={{ minHeight: 300 }}>
            {chartData.length > 0 ? (
              <Suspense fallback={<div className="chart-placeholder"><div className="chart-label">Loading chart...</div></div>}>
                <StatsChart
                  data={chartData}
                  label={metricOptions[metric] ?? metric}
                  showEvAdjusted={metric === "profit" && showAdjusted}
                  showRolling={rollingWindow > 1}
                />
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
        <div className="panel ev-leak-panel">
          <div className="panel-header">
            <h2>EV Leak Lab</h2>
            <p>
              {evReport
                ? `${evReport.priced_decision_count} priced decision(s), ${evReport.mistake_count} costly spot(s)`
                : "Play priced decisions with training enabled to populate EV leaks."}
            </p>
          </div>
          <div className="ev-leak-summary">
            <div className="stat-card">
              <div className="stat-label">EV Lost</div>
              <div className="stat-value warn">{formatBb(evReport?.total_ev_loss_bb)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Worst Group</div>
              <div className="stat-value">
                {evReport?.worst_group
                  ? `${evReport.worst_group.street} ${evReport.worst_group.chosen_action}`
                  : "-"}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Sample</div>
              <div className="stat-value">{evReport?.priced_decision_count ?? 0}</div>
            </div>
          </div>
          <div className="ev-leak-table">
            <div className="ev-leak-row header">
              <span>Spot</span>
              <span>Chosen</span>
              <span>Recommended</span>
              <span>Loss</span>
              <span>Count</span>
            </div>
            {(evReport?.groups ?? []).map((group) => (
              <div
                className="ev-leak-row"
                key={`${group.street}-${group.position}-${group.chosen_action}-${group.recommended_action}-${group.opponent_type}`}
              >
                <span>{group.street} / pos {group.position} / {group.opponent_type}</span>
                <span>{group.chosen_action}</span>
                <span>{group.recommended_action}</span>
                <span>{formatBb(group.total_ev_loss_bb)}</span>
                <span>{group.decision_count}</span>
              </div>
            ))}
            {(!evReport || evReport.groups.length === 0) && (
              <div className="ev-leak-row">
                <span>No EV leaks recorded yet.</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Track-3 regret heatmap. Shows EV-loss density by street x
          SPR; clicking a cell seeds a drill from that exact spot. */}
      <section className="section">
        <RegretHeatmap player={player} />
      </section>

      {/* Quant-flavored variance + risk metrics. The realized-vs-EV
          line is a luck-adjusted winrate plot; the four cards
          summarize std-dev, RoR, Kelly, and all-in luck. */}
      <section className="section">
        <VariancePanel player={player} />
      </section>

      {/* ICM equity calculator. Useful for tournament players;
          renders a chip-leader-vs-shortstack table and computes
          risk premium / bubble factor for hero's seat. */}
      <section className="section">
        <IcmPanel player={player} />
      </section>

      {/* Track 5 range-vs-range equity. Pure tool — pick a preflop
          chart for each side, optionally a board, and run the
          Monte Carlo with proper card removal. */}
      <section className="section">
        <RangeEquityPanel />
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

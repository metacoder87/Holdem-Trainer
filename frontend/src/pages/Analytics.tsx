import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import StatsChart from "../components/StatsChart";
import { getAnalyticsReport, getChartData, type AnalyticsReport } from "../api/client";

type ChartPoint = {
  label: string;
  value: number;
};

export default function Analytics() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const player = activePlayer || "Guest";

    // Fetch chart data
    const fetchHistory = async () => {
      try {
        const data = await getChartData("vpip", player);
        setChartData(data);
      } catch (err) {
        setChartData([]);
        setStatus(err instanceof Error ? err.message : "Failed to fetch chart data.");
      }
    };

    // Fetch deep analytics report
    const fetchReport = async () => {
      try {
        const data = await getAnalyticsReport(player);
        setReport(data);
      } catch (e) {
        setReport(null);
        setStatus(e instanceof Error ? e.message : "Failed to fetch analytics report.");
      }
    };

    fetchHistory();
    fetchReport();
  }, [activePlayer]);

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Analytics</h2>
          <p>Track trends, leaks, and performance momentum over time.</p>
        </div>
        {status && <div className="form-status">{status}</div>}
        <div className="hero-stats">
          {summary.live_metrics.map((metric) => (
            <div key={metric.label} className="stat-card">
              <div className="stat-label">{metric.label}</div>
              <div className={`stat-value ${metric.tone}`}>{metric.value}</div>
              <div className={`stat-delta ${metric.tone}`}>{metric.delta}</div>
            </div>
          ))}
          {/* Strategy Score Card */}
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
            <p>VPIP Trend (Last 10 Sessions)</p>
          </div>
          <div className="chart-container" style={{ minHeight: 300 }}>
            {chartData.length > 0 ? (
              <StatsChart data={chartData} label="VPIP %" />
            ) : (
              <div className="chart-placeholder">
                <div className="chart-grid" />
                <div className="chart-label">Play tracked sessions to populate VPIP trends</div>
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Leak Radar</h2>
            <p>Auto-detected leaks from your {report?.playing_style.player_type || "Unknown"} profile.</p>
          </div>
          {report ? (
            <ul className="focus-list">
              {report.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
              {report.recommendations.length === 0 && (
                <li className="text-slate-500">No major leaks detected. Great job!</li>
              )}
            </ul>
          ) : (
            <div className="p-4 text-slate-400">Loading analysis...</div>
          )}
        </div>
      </section>
    </>
  );
}

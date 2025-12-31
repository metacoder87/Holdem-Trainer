import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";

export default function Analytics() {
  const { summary } = useOutletContext<ShellContext>();

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Analytics</h2>
          <p>Track trends, leaks, and performance momentum over time.</p>
        </div>
        <div className="hero-stats">
          {summary.live_metrics.map((metric) => (
            <div key={metric.label} className="stat-card">
              <div className="stat-label">{metric.label}</div>
              <div className={`stat-value ${metric.tone}`}>{metric.value}</div>
              <div className={`stat-delta ${metric.tone}`}>{metric.delta}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Trend Overview</h2>
            <p>Charts will render here once analytics endpoints are wired.</p>
          </div>
          <div className="chart-placeholder">
            <div className="chart-grid" />
            <div className="chart-label">VPIP / PFR / Aggression timeline</div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Leak Radar</h2>
            <p>Auto-detected leaks prioritized by EV impact.</p>
          </div>
          <ul className="focus-list">
            <li>River bluff frequency below target</li>
            <li>Under-defending vs 3-bets out of position</li>
            <li>Turn check-raise imbalance</li>
            <li>Missed thin value in position</li>
          </ul>
        </div>
      </section>
    </>
  );
}

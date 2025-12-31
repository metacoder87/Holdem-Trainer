import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";

export default function Table() {
  const { summary } = useOutletContext<ShellContext>();

  return (
    <>
      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Live Table</h2>
            <p>Start a training session or jump into a replayed hand.</p>
          </div>
          <div className="table-canvas">
            <NeonTable />
          </div>
          <div className="hero-actions">
            <Link className="btn primary" to="/games">
              Start Session
            </Link>
            <Link className="btn ghost" to="/replay">
              Watch Replay
            </Link>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Session Snapshot</h2>
            <p>Latest performance signals from {summary.player.name}.</p>
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
          <div className="timeline">
            {summary.timeline.map((entry) => (
              <div key={`${entry.time}-${entry.label}`} className="timeline-item">
                <div className="timeline-time">{entry.time}</div>
                <div className="timeline-body">
                  <div className="timeline-label">{entry.label}</div>
                  <div className="timeline-detail">{entry.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";

export default function Home() {
  const { summary } = useOutletContext<ShellContext>();

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow fade-up delay-1">Realtime coaching and cinematic feedback</p>
          <h1 className="hero-title fade-up delay-2">
            Master Texas Holdem with a neon-speed training engine
          </h1>
          <p className="hero-lead fade-up delay-3">
            Build mastery with range-based drills, live HUD overlays, and a
            precision replay vault. Every decision is graded, tracked, and
            turned into the next lesson.
          </p>
          <div className="hero-actions fade-up delay-4">
            <Link className="btn primary" to="/training">
              Start Training
            </Link>
            <Link className="btn ghost" to="/games">
              Open Lobby
            </Link>
            <Link className="btn ghost" to="/replay">
              Open Replay Vault
            </Link>
          </div>
          <div className="hero-stats fade-up delay-5">
            {summary.live_metrics.map((metric) => (
              <div key={metric.label} className="stat-card">
                <div className="stat-label">{metric.label}</div>
                <div className={`stat-value ${metric.tone}`}>{metric.value}</div>
                <div className={`stat-delta ${metric.tone}`}>{metric.delta}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="hero-visual fade-up delay-2">
          <div className="table-shell">
            <div className="table-canvas">
              <NeonTable />
            </div>
            <div className="table-controls">
              <div className="control-chip">Fold</div>
              <div className="control-chip">Call 1.2k</div>
              <div className="control-chip primary">Raise 3.1k</div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-header">
          <h2>Training Modules</h2>
          <p>
            Precision curriculum built for tournament and cash mastery, with
            drills that adapt to your leaks.
          </p>
        </div>
        <div className="card-grid">
          {summary.training_tracks.map((track) => (
            <div key={track.title} className="panel module-card">
              <div className="module-label">{track.cadence}</div>
              <h3>{track.title}</h3>
              <p>{track.summary}</p>
              <div className="module-footer">
                <span className="module-intensity">{track.intensity}</span>
                <div className="progress">
                  <span style={{ width: `${track.progress}%` }} />
                </div>
                <span className="progress-text">{track.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section split">
        <div className="panel focus-panel">
          <div className="panel-header">
            <h2>Focus Queue</h2>
            <p>Next up in your personalized study path.</p>
          </div>
          <ul className="focus-list">
            {summary.focus_queue.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <Link className="btn primary" to="/training/drill">
            Launch Drill Set
          </Link>
        </div>

        <div className="panel timeline-panel">
          <div className="panel-header">
            <h2>Session Timeline</h2>
            <p>Live grading with instant corrections.</p>
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
          <Link className="btn ghost" to="/replay">
            Review Session
          </Link>
        </div>
      </section>
    </>
  );
}

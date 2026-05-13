import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";

export default function Home() {
  const { summary } = useOutletContext<ShellContext>();

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow fade-up delay-1">Tracked play, drills, and replay review</p>
          <h1 className="hero-title fade-up delay-2">
            Practice Texas Holdem with a measured training loop
          </h1>
          <p className="hero-lead fade-up delay-3">
            Play tracked sessions, answer server-graded quizzes, review saved
            hands, and turn detected leaks into focused drills.
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
              <NeonTable
                pot="$3.8K POT"
                action="Turn decision"
                heroCards={["A♠", "K♥"]}
                communityCards={["10♦", "J♣", "Q♠", "2♥"]}
                players={[
                  { name: "Hero", bankroll: 12800, current_bet: 1200, folded: false, all_in: false, isHero: true },
                  { name: "Vega", bankroll: 9400, current_bet: 1200, folded: false, all_in: false },
                  { name: "Nyx", bankroll: 0, current_bet: 0, folded: true, all_in: false },
                  { name: "Cipher", bankroll: 5200, current_bet: 0, folded: false, all_in: false }
                ]}
              />
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
            Current tracks are generated from recorded session metrics and
            completed training attempts.
          </p>
        </div>
        <div className="card-grid">
          {summary.training_tracks.length > 0 ? summary.training_tracks.map((track) => (
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
          )) : (
            <div className="panel module-card">
              <div className="module-label">No data</div>
              <h3>Play a tracked session</h3>
              <p>Training modules appear once this profile has recorded hands.</p>
            </div>
          )}
        </div>
      </section>

      <section className="section split">
        <div className="panel focus-panel">
          <div className="panel-header">
            <h2>Focus Queue</h2>
            <p>Next up from your recorded leaks and study recommendations.</p>
          </div>
          <ul className="focus-list">
            {summary.focus_queue.length > 0 ? summary.focus_queue.map((item) => (
              <li key={item}>{item}</li>
            )) : <li>No focus items yet.</li>}
          </ul>
          <Link className="btn primary" to="/training/drill">
            Launch Drill Set
          </Link>
        </div>

        <div className="panel timeline-panel">
          <div className="panel-header">
            <h2>Session Timeline</h2>
            <p>Recent tracked hands for this profile.</p>
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

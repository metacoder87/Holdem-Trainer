import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import { getHandHistory, type HandHistory } from "../api/client";

export default function Replay() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [hands, setHands] = useState<HandHistory[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const player = activePlayer || summary.player.name;
    getHandHistory(player, 25)
      .then((data) => {
        setHands(data);
        setStatus(null);
      })
      .catch((err) => {
        console.error(err);
        setStatus(err.message || "Failed to load hand history");
      });
  }, [activePlayer, summary.player.name]);

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Replay Vault</h2>
          <p>Review hand histories with grading overlays and coach notes.</p>
        </div>
        {activePlayer || summary.player.name ? (
          <div className="card-grid">
            {hands.length > 0 ? (
              hands.map((hand, index) => (
                <div key={hand.hand_number ?? index} className="panel module-card">
                  <div className="module-label">Hand {hand.hand_number ?? "-"}</div>
                  <h3>{hand.hero_hole_cards?.join(" ") || "Unknown cards"}</h3>
                  <p>Board: {hand.board?.join(" ") || "No board yet"}</p>
                  <div className="module-footer">
                    <span className="module-intensity">
                      Pot ${hand.pot_total ?? 0}
                    </span>
                    <Link className="btn ghost" to={`/replay/${hand.hand_number ?? index + 1}`}>
                      Open Hand
                    </Link>
                  </div>
                </div>
              ))
            ) : (
              <div className="panel module-card">
                <div className="module-label">No hands</div>
                <h3>No hand history found</h3>
                <p>Play a session to populate the replay vault.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="panel module-card">
            <div className="module-label">Select Player</div>
            <h3>No active player selected</h3>
            <p>Pick an active player in the bankroll tab to load replays.</p>
            <Link className="btn primary" to="/bankroll">
              Open Bankroll
            </Link>
          </div>
        )}
        {status && <div className="form-status">{status}</div>}
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Filters</h2>
            <p>Slice hands by position, stack depth, or opponent type.</p>
          </div>
          <ul className="focus-list">
            <li>Button opens vs blinds</li>
            <li>Short stack all-ins</li>
            <li>River bluff catchers</li>
            <li>Multiway pots</li>
          </ul>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Coach Notes</h2>
            <p>Summary highlights and tagged mistakes.</p>
          </div>
          <div className="timeline">
            {summary.timeline.map((entry) => (
              <div key={`${entry.time}-${entry.label}-note`} className="timeline-item">
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

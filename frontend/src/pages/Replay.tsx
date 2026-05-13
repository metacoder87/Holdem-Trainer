import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import { getFilteredHands, getHandHistory, type HandHistory } from "../api/client";

export default function Replay() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [hands, setHands] = useState<HandHistory[]>([]);
  const [winner, setWinner] = useState("");
  const [street, setStreet] = useState("");
  const [decisionQuality, setDecisionQuality] = useState("");
  const [minPot, setMinPot] = useState("");
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

  const applyFilters = async () => {
    const player = activePlayer || summary.player.name;
    try {
      const data = await getFilteredHands(player, {
        winner: winner || undefined,
        street: street || undefined,
        decisionQuality: decisionQuality || undefined,
        minPot: minPot ? Number(minPot) : undefined,
        limit: 25
      });
      setHands(data);
      setStatus(null);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to filter hand history");
    }
  };

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
            <p>Slice hands by result, pot size, street, or decision grade.</p>
          </div>
          <div className="filter-grid">
            <label>
              Winner
              <select value={winner} onChange={(event) => setWinner(event.target.value)}>
                <option value="">Any</option>
                <option value="hero">Hero</option>
                <option value="Villain">Villain</option>
              </select>
            </label>
            <label>
              Street
              <select value={street} onChange={(event) => setStreet(event.target.value)}>
                <option value="">Any</option>
                <option value="preflop">Preflop</option>
                <option value="flop">Flop</option>
                <option value="turn">Turn</option>
                <option value="river">River</option>
              </select>
            </label>
            <label>
              Decision grade
              <select value={decisionQuality} onChange={(event) => setDecisionQuality(event.target.value)}>
                <option value="">Any</option>
                <option value="optimal">Optimal</option>
                <option value="acceptable">Acceptable</option>
                <option value="suboptimal">Suboptimal</option>
              </select>
            </label>
            <label>
              Min pot
              <input type="number" value={minPot} onChange={(event) => setMinPot(event.target.value)} />
            </label>
          </div>
          <div className="hero-actions">
            <button className="btn primary" type="button" onClick={applyFilters}>
              Apply Filters
            </button>
          </div>
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

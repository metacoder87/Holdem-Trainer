import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  getHandReplay,
  type HandReplay,
  type ReplayStreet
} from "../api/client";

const STREET_LABELS: Record<ReplayStreet["name"], string> = {
  preflop: "Preflop",
  flop: "Flop",
  turn: "Turn",
  river: "River"
};

function qualityTone(quality?: string): string {
  if (!quality) return "warn";
  if (quality === "optimal") return "good";
  if (quality === "acceptable") return "good";
  if (quality === "suboptimal") return "warn";
  return "warn";
}

export default function ReplayDetail() {
  const { activePlayer } = useOutletContext<ShellContext>();
  const { handNumber } = useParams<{ handNumber: string }>();
  const [replay, setReplay] = useState<HandReplay | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streetIndex, setStreetIndex] = useState(0);

  useEffect(() => {
    if (!activePlayer || !handNumber) return;
    setReplay(null);
    setError(null);
    setStreetIndex(0);
    getHandReplay(activePlayer, Number(handNumber))
      .then((data) => setReplay(data))
      .catch((err) => setError(err.message || "Failed to load replay"));
  }, [activePlayer, handNumber]);

  const currentStreet = useMemo<ReplayStreet | null>(() => {
    if (!replay || replay.streets.length === 0) return null;
    return replay.streets[Math.min(streetIndex, replay.streets.length - 1)];
  }, [replay, streetIndex]);

  if (!activePlayer) {
    return (
      <section className="section">
        <div className="panel module-card">
          <div className="module-label">Select Player</div>
          <h3>No active player selected</h3>
          <Link className="btn primary" to="/bankroll">
            Open Bankroll
          </Link>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="section">
        <div className="panel module-card">
          <h3>Replay unavailable</h3>
          <p>{error}</p>
          <Link className="btn ghost" to="/replay">
            Back to Replay Vault
          </Link>
        </div>
      </section>
    );
  }

  if (!replay || !currentStreet) {
    return (
      <section className="section">
        <div className="panel">
          <div className="panel-header">
            <h2>Loading replay...</h2>
          </div>
        </div>
      </section>
    );
  }

  const totalStreets = replay.streets.length;

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Replay - Hand #{replay.hand_number ?? "-"}</h2>
          <p>
            {replay.summary.game_type ?? "cash"} ({replay.summary.limit_type ?? "no_limit"}) - blinds{" "}
            {replay.summary.small_blind ?? "?"}/{replay.summary.big_blind ?? "?"}
            {replay.summary.ante ? ` ante ${replay.summary.ante}` : ""}
          </p>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>{STREET_LABELS[currentStreet.name]}</h2>
            <p>
              Board: {currentStreet.board.length > 0 ? currentStreet.board.join(" ") : "-"}
            </p>
          </div>

          <div className="hero-actions">
            <button
              className="btn ghost"
              type="button"
              disabled={streetIndex === 0}
              onClick={() => setStreetIndex((i) => Math.max(0, i - 1))}
            >
              Previous Street
            </button>
            <button
              className="btn primary"
              type="button"
              disabled={streetIndex >= totalStreets - 1}
              onClick={() => setStreetIndex((i) => Math.min(totalStreets - 1, i + 1))}
            >
              Next Street
            </button>
            <Link className="btn ghost" to="/replay">
              Back to List
            </Link>
          </div>

          <div className="session-readout">
            <div className="demo-row">
              <span>Hero Cards</span>
              <span>{replay.hero_hole_cards.join(" ") || "-"}</span>
            </div>
            <div className="demo-row">
              <span>Winners</span>
              <span>{replay.winners.join(", ") || "-"}</span>
            </div>
            <div className="demo-row">
              <span>Pot</span>
              <span>${replay.pot_total}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Actions</h2>
            <p>{currentStreet.actions.length} actions on this street</p>
          </div>
          <div className="timeline">
            {currentStreet.actions.length === 0 && (
              <div className="timeline-item">
                <div className="timeline-body">
                  <div className="timeline-label">No actions</div>
                  <div className="timeline-detail">Street had no betting activity.</div>
                </div>
              </div>
            )}
            {currentStreet.actions.map((action, index) => (
              <div key={`${action.player}-${index}`} className="timeline-item">
                <div className="timeline-time">{action.player}</div>
                <div className="timeline-body">
                  <div className="timeline-label">
                    {action.action.toUpperCase()}
                    {action.amount > 0 ? ` $${action.amount}` : ""}
                  </div>
                  <div className="timeline-detail">
                    Pot ${action.pot_before} -&gt; ${action.pot_after}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Decision Grades</h2>
            <p>Hero choices vs. recommended action</p>
          </div>
          <div className="timeline">
            {currentStreet.decisions.length === 0 && (
              <div className="timeline-item">
                <div className="timeline-body">
                  <div className="timeline-label">No graded decisions</div>
                  <div className="timeline-detail">No hero action recorded on this street.</div>
                </div>
              </div>
            )}
            {currentStreet.decisions.map((decision, index) => {
              const reasoning = decision.analysis?.reasoning;
              const reasoningLines = Array.isArray(reasoning)
                ? reasoning
                : typeof reasoning === "string"
                ? [reasoning]
                : [];
              const facts: string[] = [];
              if (typeof decision.equity === "number") {
                facts.push(`Equity ${(decision.equity * 100).toFixed(0)}%`);
              }
              if (typeof decision.required_equity === "number") {
                facts.push(`Need ${(decision.required_equity * 100).toFixed(0)}%`);
              }
              if (typeof decision.hand_strength === "number") {
                facts.push(`Strength ${(decision.hand_strength * 100).toFixed(0)}%`);
              }
              if (typeof decision.hand_potential === "number" && decision.hand_potential > 0) {
                facts.push(`Potential ${(decision.hand_potential * 100).toFixed(0)}%`);
              }
              if (decision.opponent?.type && decision.opponent.type !== "unknown") {
                facts.push(`Vs ${decision.opponent.type}`);
              }
              return (
                <div key={index} className="timeline-item">
                  <div className="timeline-time">{(decision.chosen_action ?? "-").toUpperCase()}</div>
                  <div className="timeline-body">
                    <div className={`timeline-label ${qualityTone(decision.quality)}`}>
                      {(decision.quality ?? "ungraded").toUpperCase()}
                    </div>
                    <div className="timeline-detail">
                      Recommended: {decision.recommended_action ?? "-"}
                      {facts.length > 0 && (
                        <span> ({facts.join(", ")})</span>
                      )}
                    </div>
                    {(reasoningLines.length > 0 || decision.analysis?.grade_method) && (
                      <details className="quiz-explain" style={{ marginTop: 8 }}>
                        <summary>Why</summary>
                        {decision.analysis?.grade_method && (
                          <div className="timeline-detail">
                            Method: {decision.analysis.grade_method}
                          </div>
                        )}
                        {reasoningLines.length > 0 && (
                          <pre style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>
                            {reasoningLines.join("\n")}
                          </pre>
                        )}
                      </details>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </>
  );
}

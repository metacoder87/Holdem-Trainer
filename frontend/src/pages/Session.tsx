import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";
import {
  ApiError,
  getGameHandState,
  getGameSession,
  startGameHand,
  submitGameInput,
  type GameHandState,
  type GameSession
} from "../api/client";
import { useSessionSocket } from "../api/useSessionSocket";

export default function Session() {
  const { summary } = useOutletContext<ShellContext>();
  const [session, setSession] = useState<GameSession | null>(null);
  const [handState, setHandState] = useState<GameHandState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingValue, setPendingValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Only open the WebSocket once the session has been verified via HTTP -
  // otherwise a stale localStorage id would dial a 4404 close immediately.
  const socket = useSessionSocket(session?.id ?? null);

  useEffect(() => {
    const sessionId = localStorage.getItem("ph_session_id");
    if (!sessionId) return;

    getGameSession(sessionId)
      .then((data) => {
        setSession(data);
        getGameHandState(sessionId)
          .then((handData) => setHandState(handData))
          .catch(() => null);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          // Stale id (e.g. from a previous server run). Clear it silently.
          localStorage.removeItem("ph_session_id");
          setSession(null);
          setHandState(null);
          setStatus(null);
          return;
        }
        setStatus(err instanceof Error ? err.message : "Failed to load session");
      });
  }, []);

  // Push WebSocket state into local state (the canonical source of truth).
  useEffect(() => {
    if (socket.state) {
      setHandState(socket.state);
    }
  }, [socket.state]);

  const startHand = useCallback(
    async (message?: string) => {
      if (!session) return;
      setSubmitting(true);
      try {
        if (socket.status === "open") {
          socket.startHand();
        } else {
          const nextState = await startGameHand(session.id);
          setHandState(nextState);
        }
        setStatus(message ?? null);
      } catch (err) {
        if (err instanceof Error) setStatus(err.message);
      } finally {
        setSubmitting(false);
      }
    },
    [session, socket]
  );

  useEffect(() => {
    if (!session) return;
    if (localStorage.getItem("ph_autoplay") !== "1") return;
    localStorage.removeItem("ph_autoplay");
    startHand("Gameplay started. Awaiting first action.");
  }, [session, startHand]);

  const pending = handState?.pending_input || null;
  const gameState = handState?.state;
  const tournamentResult = handState?.tournament_result || null;

  const submitValue = async (value: number | boolean | string, choice?: number) => {
    if (!session) return;
    setSubmitting(true);
    try {
      if (socket.status === "open") {
        socket.submitInput(choice ?? value);
      } else {
        const payload = choice !== undefined ? { choice } : { value };
        const nextState = await submitGameInput(session.id, payload);
        setHandState(nextState);
      }
      setStatus(null);
    } catch (err) {
      if (err instanceof Error) setStatus(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleChoice = (choice: number) => submitValue(choice, choice);

  const handleNumberSubmit = async () => {
    if (!session || !pending) return;
    const value = Number(pendingValue);
    if (Number.isNaN(value)) {
      setStatus("Enter a numeric value.");
      return;
    }
    await submitValue(value);
    setPendingValue("");
  };

  const handleYesNo = (value: boolean) => submitValue(value);

  const handStatus = handState?.status;
  let actionContent = (
    <button className="btn primary" type="button" onClick={() => startHand()} disabled={!session}>
      Start Next Hand
    </button>
  );

  if (!pending && handStatus === "in_hand") {
    actionContent = <div className="module-intensity">Hand in progress...</div>;
  }

  if (handStatus === "tournament_complete") {
    actionContent = (
      <div className="module-intensity">
        Tournament finished. Open the bankroll tab to see your final cash.
      </div>
    );
  } else if (pending?.kind === "menu") {
    actionContent = (
      <div className="action-grid">
        {(pending.options || []).map((option, index) => (
          <button
            key={`${option}-${index}`}
            className="btn ghost"
            type="button"
            onClick={() => handleChoice(index + 1)}
            disabled={submitting}
          >
            {option}
          </button>
        ))}
      </div>
    );
  } else if (pending?.kind === "number") {
    actionContent = (
      <div className="action-input">
        <label>
          Amount
          <input
            type="number"
            min={pending.min_value ?? undefined}
            max={pending.max_value ?? undefined}
            step={pending.integer_only ? 1 : 0.5}
            value={pendingValue}
            onChange={(event) => setPendingValue(event.target.value)}
          />
        </label>
        <button className="btn primary" type="button" onClick={handleNumberSubmit} disabled={submitting}>
          Submit
        </button>
      </div>
    );
  } else if (pending?.kind === "yes_no") {
    actionContent = (
      <div className="action-grid">
        <button className="btn primary" type="button" onClick={() => handleYesNo(true)} disabled={submitting}>
          Yes
        </button>
        <button className="btn ghost" type="button" onClick={() => handleYesNo(false)} disabled={submitting}>
          No
        </button>
      </div>
    );
  }

  const lastHand = handState?.last_hand;
  const lastHandNumber = lastHand?.hand_number;

  return (
    <>
      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Live Session</h2>
            <p>
              {session ? `Session ${session.id}` : "Create a session in the game lobby."}
              {session && (
                <span style={{ marginLeft: 8 }}>
                  ({socket.status === "open" ? "WS live" : `WS ${socket.status}`})
                </span>
              )}
            </p>
          </div>
          {!session && (
            <Link className="btn primary" to="/games">
              Open Game Lobby
            </Link>
          )}
          <div className="table-canvas">
            <NeonTable liveState={gameState ?? null} heroName={gameState?.hero_name ?? null} />
          </div>
          <div className="hero-actions">
            <button
              className="btn primary"
              type="button"
              onClick={() => startHand()}
              disabled={!session || submitting || Boolean(pending) || handStatus === "tournament_complete"}
            >
              {handStatus === "tournament_complete"
                ? "Tournament Over"
                : pending
                ? "Awaiting Action"
                : "Play Next Hand"}
            </button>
            {lastHandNumber ? (
              <Link className="btn ghost" to={`/replay/${lastHandNumber}`}>
                Review Last Hand
              </Link>
            ) : (
              <Link className="btn ghost" to="/replay">
                Open Replay Vault
              </Link>
            )}
          </div>

          {tournamentResult && (
            <div className={`quiz-result ${tournamentResult.result === "won" ? "good" : "warn"}`}>
              <strong>Tournament {tournamentResult.result.toUpperCase()}.</strong>{" "}
              Cash bankroll restored to ${tournamentResult.final_bankroll.toLocaleString()}
              {tournamentResult.result === "won"
                ? "."
                : tournamentResult.result === "lost"
                ? " (no payout)."
                : "."}
            </div>
          )}

          {lastHand?.coach_notes && handStatus === "hand_complete" && (
            <div className="panel" style={{ marginTop: 12, padding: 14 }}>
              <div className="panel-header" style={{ marginBottom: 6 }}>
                <h3 style={{ margin: 0 }}>
                  Coach notes - Hand grade{" "}
                  <span className={lastHand.coach_notes.hero_won ? "good" : "warn"}>
                    {lastHand.coach_notes.hand_grade}
                  </span>
                </h3>
                <p style={{ margin: 0 }}>{lastHand.coach_notes.headline}</p>
              </div>
              {lastHand.coach_notes.takeaway && (
                <div className="timeline-detail" style={{ marginTop: 6 }}>
                  {lastHand.coach_notes.takeaway}
                </div>
              )}
              {lastHand.coach_notes.worst_decision && (
                <div
                  className={`timeline-detail ${
                    lastHand.coach_notes.worst_decision.quality === "suboptimal" ? "warn" : ""
                  }`}
                  style={{ marginTop: 4 }}
                >
                  Biggest leak: {lastHand.coach_notes.worst_decision.line}
                </div>
              )}
              {lastHandNumber && (
                <div style={{ marginTop: 8 }}>
                  <Link className="btn ghost" to={`/replay/${lastHandNumber}`}>
                    Review full hand
                  </Link>
                </div>
              )}
            </div>
          )}

          <div className="action-panel">
            <div className="panel-header">
              <h3>Action Console</h3>
              <p>{pending ? pending.prompt : "Start a hand to receive actions."}</p>
            </div>
            {actionContent}
            {(handState?.error || handState?.input_error || status) && (
              <div className="form-status">
                {handState?.error || handState?.input_error || status}
              </div>
            )}
          </div>

          {gameState && (
            <div className="session-readout">
              <div className="demo-row">
                <span>Phase</span>
                <span>{gameState.game_state}</span>
              </div>
              <div className="demo-row">
                <span>Hero Cards</span>
                <span>{gameState.hero_cards?.join(" ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Board</span>
                <span>{gameState.community_cards?.join(" ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Pot</span>
                <span>${gameState.pot_size ?? 0}</span>
              </div>
              <div className="demo-row">
                <span>Blinds</span>
                <span>
                  {gameState.blinds?.small_blind ?? "-"} / {gameState.blinds?.big_blind ?? "-"}
                </span>
              </div>
            </div>
          )}

          {gameState?.hud?.opponents && gameState.hud.opponents.length > 0 && (
            <div className="panel" style={{ marginTop: 12, padding: 10 }}>
              <div className="panel-header" style={{ marginBottom: 6 }}>
                <h3 style={{ margin: 0 }}>HUD</h3>
                <p style={{ margin: 0 }}>Opponent profile (VPIP / PFR / AF)</p>
              </div>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", opacity: 0.75 }}>
                    <th>Player</th>
                    <th>Type</th>
                    <th>Hands</th>
                    <th>VPIP</th>
                    <th>PFR</th>
                    <th>AF</th>
                  </tr>
                </thead>
                <tbody>
                  {gameState.hud.opponents.map((opp) => (
                    <tr key={opp.name}>
                      <td>{opp.name}</td>
                      <td>{opp.type}</td>
                      <td>{opp.hands}</td>
                      <td>{(opp.vpip * 100).toFixed(0)}%</td>
                      <td>{(opp.pfr * 100).toFixed(0)}%</td>
                      <td>
                        {opp.aggression_factor >= 99
                          ? "∞"
                          : opp.aggression_factor.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {lastHand && (
            <div className="demo-hand" style={{ marginTop: 16 }}>
              <div className="demo-row">
                <span>Last Hand</span>
                <span>
                  {lastHandNumber ? (
                    <Link to={`/replay/${lastHandNumber}`}>#{lastHandNumber}</Link>
                  ) : (
                    "-"
                  )}
                </span>
              </div>
              <div className="demo-row">
                <span>Winners</span>
                <span>{lastHand.winners?.join(", ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Pot</span>
                <span>${lastHand.pot_total ?? 0}</span>
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Live Coaching</h2>
            <p>Real-time feedback pipeline for {summary.player.name}.</p>
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
          <Link className="btn ghost" to="/training">
            Adjust Training Plan
          </Link>
        </div>
      </section>
    </>
  );
}

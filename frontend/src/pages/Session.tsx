import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";
import {
  getGameHandState,
  getGameSession,
  startGameHand,
  submitGameInput,
  type GameHandState,
  type GameSession
} from "../api/client";

export default function Session() {
  const { summary } = useOutletContext<ShellContext>();
  const [session, setSession] = useState<GameSession | null>(null);
  const [handState, setHandState] = useState<GameHandState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingValue, setPendingValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const sessionId = localStorage.getItem("ph_session_id");
    if (!sessionId) return;
    getGameSession(sessionId)
      .then((data) => setSession(data))
      .catch((err) => setStatus(err.message || "Failed to load session"));
    getGameHandState(sessionId)
      .then((data) => setHandState(data))
      .catch(() => null);
  }, []);

  const startHand = useCallback(
    async (message?: string) => {
      if (!session) return;
      setSubmitting(true);
      try {
        const nextState = await startGameHand(session.id);
        setHandState(nextState);
        if (message) {
          setStatus(message);
        } else {
          setStatus(null);
        }
      } catch (err) {
        if (err instanceof Error) {
          setStatus(err.message);
        }
      } finally {
        setSubmitting(false);
      }
    },
    [session]
  );

  useEffect(() => {
    if (!session) return;
    if (localStorage.getItem("ph_autoplay") !== "1") return;
    localStorage.removeItem("ph_autoplay");
    startHand("Gameplay started. Awaiting first action.");
  }, [session, startHand]);

  useEffect(() => {
    if (!session || !handState) return;
    if (handState.pending_input || handState.status !== "in_hand") return;
    const timer = window.setTimeout(() => {
      getGameHandState(session.id)
        .then((data) => setHandState(data))
        .catch(() => null);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [handState, session]);

  const pending = handState?.pending_input || null;
  const gameState = handState?.state;

  const handleChoice = async (choice: number) => {
    if (!session) return;
    setSubmitting(true);
    try {
      const nextState = await submitGameInput(session.id, { choice });
      setHandState(nextState);
      setStatus(null);
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleNumberSubmit = async () => {
    if (!session || !pending) return;
    const value = Number(pendingValue);
    if (Number.isNaN(value)) {
      setStatus("Enter a numeric value.");
      return;
    }
    setSubmitting(true);
    try {
      const nextState = await submitGameInput(session.id, { value });
      setHandState(nextState);
      setStatus(null);
      setPendingValue("");
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleYesNo = async (value: boolean) => {
    if (!session) return;
    setSubmitting(true);
    try {
      const nextState = await submitGameInput(session.id, { value });
      setHandState(nextState);
      setStatus(null);
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handStatus = handState?.status;
  let actionContent = (
    <button className="btn primary" type="button" onClick={() => startHand()} disabled={!session}>
      Start Next Hand
    </button>
  );

  if (!pending && handStatus === "in_hand") {
    actionContent = <div className="module-intensity">Hand in progress...</div>;
  }

  if (pending?.kind === "menu") {
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

  return (
    <>
      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Live Session</h2>
            <p>{session ? `Session ${session.id}` : "Create a session in the game lobby."}</p>
          </div>
          {!session && (
            <Link className="btn primary" to="/games">
              Open Game Lobby
            </Link>
          )}
          <div className="table-canvas">
            <NeonTable />
          </div>
          <div className="hero-actions">
            <button
              className="btn primary"
              type="button"
              onClick={() => startHand()}
              disabled={!session || submitting || Boolean(pending)}
            >
              {pending ? "Awaiting Action" : "Play Next Hand"}
            </button>
            <Link className="btn ghost" to="/replay">
              Review Last Hand
            </Link>
          </div>

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

          {handState?.last_hand && (
            <div className="demo-hand" style={{ marginTop: 16 }}>
              <div className="demo-row">
                <span>Last Hand</span>
                <span>#{handState.last_hand.hand_number ?? "-"}</span>
              </div>
              <div className="demo-row">
                <span>Winners</span>
                <span>{handState.last_hand.winners?.join(", ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Pot</span>
                <span>${handState.last_hand.pot_total ?? 0}</span>
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

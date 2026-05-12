import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";
import {
  getGameHandState,
  getGameSession,
  startGameHand,
  type GameHandState,
  type GameSession
} from "../api/client";
import GameControls from "../components/GameControls";

export default function Session() {
  const { summary } = useOutletContext<ShellContext>();
  const gameSurfaceRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<GameSession | null>(null);
  const [handState, setHandState] = useState<GameHandState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [isNativeFullscreen, setIsNativeFullscreen] = useState(false);
  const [isFallbackFullscreen, setIsFallbackFullscreen] = useState(false);

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

  useEffect(() => {
    const syncNativeFullscreen = () => {
      setIsNativeFullscreen(document.fullscreenElement === gameSurfaceRef.current);
    };

    document.addEventListener("fullscreenchange", syncNativeFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncNativeFullscreen);
  }, []);

  useEffect(() => {
    if (!isFallbackFullscreen) {
      return;
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsFallbackFullscreen(false);
      }
    };

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isFallbackFullscreen]);

  const toggleFullscreen = useCallback(async () => {
    const target = gameSurfaceRef.current;
    if (!target) {
      return;
    }

    if (isFallbackFullscreen) {
      setIsFallbackFullscreen(false);
      return;
    }

    if (document.fullscreenElement) {
      try {
        await document.exitFullscreen?.();
      } finally {
        setIsNativeFullscreen(false);
      }
      return;
    }

    if (typeof target.requestFullscreen !== "function") {
      setIsFallbackFullscreen(true);
      return;
    }

    try {
      await target.requestFullscreen();
      setIsNativeFullscreen(true);
    } catch {
      setIsFallbackFullscreen(true);
    }
  }, [isFallbackFullscreen]);

  const pending = handState?.pending_input || null;
  const gameState = handState?.state;
  const handStatus = handState?.status;
  const terminalReason = handState?.terminal_reason || gameState?.game_over_reason || session?.terminal_reason;
  const isGameOver = handStatus === "game_over" || Boolean(terminalReason);
  const isFullscreen = isNativeFullscreen || isFallbackFullscreen;
  const fullscreenButtonLabel = isFullscreen ? "Exit fullscreen" : "Enter fullscreen";
  const winningHandSummary = handState?.last_hand?.winning_hands
    ?.map((hand) => `${hand.player}: ${hand.rank ?? "Winning hand"}${hand.cards?.length ? ` (${hand.cards.join(" ")})` : ""}`)
    .join("; ");
  const tableAction = isGameOver
    ? `Game Over${terminalReason ? `: ${terminalReason.replace(/_/g, " ")}` : ""}`
    : handStatus === "in_hand"
      ? "Action Required"
      : (status || "Waiting...");

  return (
    <section className="section session-page">
      <div className="panel session-game-panel">
        <div
          ref={gameSurfaceRef}
          data-testid="session-game-surface"
          className={`game-surface${isFullscreen ? " is-fullscreen" : ""}${isFallbackFullscreen ? " is-fallback-fullscreen" : ""}`}
        >
          <div className="session-game-header">
            <div className="panel-header">
              <h2>Live Session</h2>
              <p>{session ? `Session ${session.id}` : "Create a session in the game lobby."}</p>
            </div>
            <button
              className="fullscreen-toggle"
              type="button"
              aria-label={fullscreenButtonLabel}
              title={fullscreenButtonLabel}
              aria-pressed={isFullscreen}
              onClick={toggleFullscreen}
            >
              <span className="fullscreen-glyph" aria-hidden="true" />
            </button>
          </div>

          {!session && (
            <Link className="btn primary session-lobby-link" to="/games">
              Open Game Lobby
            </Link>
          )}

          <div className="table-canvas session-table-canvas">
            <NeonTable
              pot={gameState?.pot_size ? `$${gameState.pot_size}` : "$0 POT"}
              action={tableAction}
              heroCards={gameState?.hero_cards || []}
              communityCards={gameState?.community_cards || []}
              players={gameState?.players || []}
            />
          </div>

          <div className="session-playbar">
            <div className="hero-actions session-hand-actions">
              <button
                className="btn primary"
                type="button"
                onClick={() => startHand()}
                disabled={!session || submitting || Boolean(pending) || isGameOver}
              >
                {isGameOver ? "Game Over" : pending ? "Awaiting Action" : "Play Next Hand"}
              </button>
              <Link className="btn ghost" to="/replay">
                Review Last Hand
              </Link>
            </div>

            <div className="action-panel session-action-panel">
              <div className="panel-header">
                <h3>Action Console</h3>
              </div>
              {session && (
                <GameControls
                  sessionId={session.id}
                  pendingInput={pending}
                  onAction={() => {
                    getGameHandState(session.id).then(setHandState).catch(() => null);
                    setStatus(null);
                  }}
                />
              )}
              {!pending && handStatus === "in_hand" && (
                <div className="module-intensity">Hand in progress...</div>
              )}
              {!pending && handStatus !== "in_hand" && !isGameOver && (
                <div className="text-slate-500 italic">Start a hand to receive actions.</div>
              )}
              {isGameOver && (
                <div className="text-slate-500 italic">
                  Session ended{terminalReason ? `: ${terminalReason.replace(/_/g, " ")}` : ""}.
                </div>
              )}

              {(handState?.error || handState?.input_error || status) && (
                <div className="form-status">
                  {handState?.error || handState?.input_error || status}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="session-secondary-grid">
        <div className="panel session-detail-panel">
          <div className="panel-header">
            <h2>Hand Readout</h2>
            <p>Current state and last-result detail.</p>
          </div>

          {gameState ? (
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
          ) : (
            <div className="text-slate-500 italic">Session telemetry appears after a hand starts.</div>
          )}

          {handState?.last_hand && (
            <div className="demo-hand last-hand-card">
              <div className="demo-row">
                <span>Last Hand</span>
                <span>#{handState.last_hand.hand_number ?? "-"}</span>
              </div>
              <div className="demo-row">
                <span>Winners</span>
                <span>{handState.last_hand.winners?.join(", ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Winning Hand</span>
                <span>
                  {handState.last_hand.won_by_fold
                    ? "Won by fold"
                    : winningHandSummary || handState.last_hand.winning_hand_rank || "-"}
                </span>
              </div>
              <div className="demo-row">
                <span>Pot</span>
                <span>${handState.last_hand.pot_total ?? 0}</span>
              </div>
            </div>
          )}
        </div>

        <div className="panel session-detail-panel">
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
      </div>
    </section>
  );
}

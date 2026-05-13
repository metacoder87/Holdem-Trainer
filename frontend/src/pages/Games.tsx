import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import {
  createGameSession,
  getGameModes,
  getGameSession,
  getGameHandState,
  startGameHand,
  type JsonValue,
  type GameHandState,
  type GameMode,
  type GameSession
} from "../api/client";
import type { ShellContext } from "../components/Shell";

export default function Games() {
  const { activePlayer } = useOutletContext<ShellContext>();
  const navigate = useNavigate();
  const [modes, setModes] = useState<GameMode[]>([]);
  const [session, setSession] = useState<GameSession | null>(null);
  const [handState, setHandState] = useState<GameHandState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [tournamentLimitType, setTournamentLimitType] = useState("no_limit");
  const [loadingMode, setLoadingMode] = useState<string | null>(null);
  const [trainingConfig, setTrainingConfig] = useState({
    training: true,
    in_game_quizzes: true,
    hud: true,
    post_hand_feedback: true
  });

  useEffect(() => {
    getGameModes()
      .then((data) => setModes(data))
      .catch((err) => setStatus(err.message || "Failed to load game modes"));
  }, []);

  useEffect(() => {
    const sessionId = localStorage.getItem("ph_session_id");
    if (!sessionId) return;
    getGameSession(sessionId)
      .then((data) => setSession(data))
      .catch((err) => setStatus(err.message || "Failed to load existing session"));
    getGameHandState(sessionId)
      .then((data) => setHandState(data))
      .catch(() => null);
  }, []);

  const resolveLimitType = (mode: GameMode) => {
    if (mode.id === "cash_limit") return "limit";
    if (mode.id === "cash_no_limit") return "no_limit";
    if (mode.id === "tournament") return tournamentLimitType;
    return "no_limit";
  };

  const createSessionForMode = async (mode: GameMode) => {
    const limitType = resolveLimitType(mode);
    setLoadingMode(mode.id);
    setStatus(null);
    try {
      const payload: Record<string, JsonValue> = {
        game_type: mode.id === "tournament" ? "tournament" : "cash",
        limit_type: limitType,
        ...trainingConfig,
        ...mode.defaults
      };
      if (activePlayer) {
        payload.player_name = activePlayer;
      }
      const newSession = await createGameSession(payload);
      setSession(newSession);
      localStorage.setItem("ph_session_id", newSession.id);
      setHandState(null);
      setStatus(`Session ${newSession.id} created.`);
      return newSession;
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
      return null;
    } finally {
      setLoadingMode(null);
    }
  };

  const handleCreate = async (mode: GameMode) => {
    await createSessionForMode(mode);
  };

  const handleStartAndPlay = async (mode: GameMode) => {
    const newSession = await createSessionForMode(mode);
    if (!newSession) return;
    localStorage.setItem("ph_autoplay", "1");
    setStatus("Gameplay started. Opening live session...");
    navigate("/session");
  };

  const handleStartHand = async () => {
    if (!session) return;
    try {
      const nextState = await startGameHand(session.id);
      setHandState(nextState);
      setStatus("Hand started. Continue in Live Session.");
      navigate("/session");
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    }
  };

  const setTrainingOption = (key: keyof typeof trainingConfig, value: boolean) => {
    setTrainingConfig((current) => {
      const next = { ...current, [key]: value };
      if (key === "training" && !value) {
        next.in_game_quizzes = false;
        next.hud = false;
        next.post_hand_feedback = false;
      }
      if (key !== "training" && value) {
        next.training = true;
      }
      return next;
    });
  };

  const terminalReason = handState?.terminal_reason || handState?.state?.game_over_reason || session?.terminal_reason;
  const isGameOver = handState?.status === "game_over" || Boolean(terminalReason);
  const winningHandSummary = handState?.last_hand?.winning_hands
    ?.map((hand) => `${hand.player}: ${hand.rank ?? "Winning hand"}${hand.cards?.length ? ` (${hand.cards.join(" ")})` : ""}`)
    .join("; ");

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Game Lobby</h2>
          <p>Spin up a new session and jump into real gameplay.</p>
        </div>
        <div className="card-grid">
          {modes.map((mode) => (
            <div key={mode.id} className="panel module-card">
              <div className="module-label">{mode.id.replace(/_/g, " ")}</div>
              <h3>{mode.label}</h3>
              <p>{mode.description}</p>
              {mode.id === "tournament" && (
                <div className="module-options">
                  <label>
                    Limit type
                    <select
                      value={tournamentLimitType}
                      onChange={(event) => setTournamentLimitType(event.target.value)}
                    >
                      <option value="no_limit">No limit</option>
                      <option value="limit">Limit</option>
                    </select>
                  </label>
                </div>
              )}
              <div className="module-options training-options">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={trainingConfig.training}
                    onChange={(event) => setTrainingOption("training", event.target.checked)}
                  />
                  Training
                </label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={trainingConfig.in_game_quizzes}
                    onChange={(event) => setTrainingOption("in_game_quizzes", event.target.checked)}
                  />
                  Quizzes
                </label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={trainingConfig.hud}
                    onChange={(event) => setTrainingOption("hud", event.target.checked)}
                  />
                  HUD
                </label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={trainingConfig.post_hand_feedback}
                    onChange={(event) => setTrainingOption("post_hand_feedback", event.target.checked)}
                  />
                  Hand review
                </label>
              </div>
              <div className="module-footer">
                <span className="module-intensity">Ready</span>
                <div className="module-actions">
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() => handleCreate(mode)}
                    disabled={loadingMode === mode.id}
                  >
                    Create Session
                  </button>
                  <button
                    className="btn primary"
                    type="button"
                    onClick={() => handleStartAndPlay(mode)}
                    disabled={loadingMode === mode.id}
                  >
                    Start Gameplay
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Active Session</h2>
            <p>{session ? `Session ${session.id}` : "No session created yet."}</p>
          </div>
          {session && (
            <>
              <div className="session-meta">
                <div>
                  <div className="stat-label">Mode</div>
                  <div className="stat-value">{session.game_type}</div>
                </div>
                <div>
                  <div className="stat-label">Limit</div>
                  <div className="stat-value">{session.limit_type}</div>
                </div>
                <div>
                  <div className="stat-label">Status</div>
                  <div className="stat-value">
                    {isGameOver ? "game_over" : handState?.status || session.status}
                  </div>
                </div>
              </div>
              <div className="hero-actions">
                <Link className="btn ghost" to="/session">
                  Open Session
                </Link>
                <button className="btn primary" type="button" onClick={handleStartHand} disabled={isGameOver}>
                  {isGameOver ? "Game Over" : "Start Next Hand"}
                </button>
              </div>
              {terminalReason && (
                <div className="form-status">Session ended: {terminalReason.replace(/_/g, " ")}.</div>
              )}
            </>
          )}
          {status && <div className="form-status">{status}</div>}
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Last Hand</h2>
            <p>Latest hand recorded for this session.</p>
          </div>
          {handState?.last_hand ? (
            <div className="demo-hand">
              <div className="demo-row">
                <span>Hand</span>
                <span>#{handState.last_hand.hand_number ?? "-"}</span>
              </div>
              <div className="demo-row">
                <span>Hero Cards</span>
                <span>{handState.last_hand.hero_hole_cards?.join(" ") || "-"}</span>
              </div>
              <div className="demo-row">
                <span>Board</span>
                <span>{handState.last_hand.board?.join(" ") || "-"}</span>
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
          ) : (
            <div className="chart-placeholder">
              <div className="chart-grid" />
              <div className="chart-label">Play a hand to populate this view</div>
            </div>
          )}
        </div>
      </section>
    </>
  );
}

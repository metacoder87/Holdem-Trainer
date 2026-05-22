import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import NeonTable from "../components/NeonTable";
import WinnerBanner from "../components/WinnerBanner";
import BetTimeline from "../components/BetTimeline";
import {
  ApiError,
  getGameHandState,
  getGameSession,
  startGameHand,
  submitGameInput,
  type GameHandState,
  type GameSession,
  type HandHistory
} from "../api/client";
import { useSessionSocket } from "../api/useSessionSocket";

function handSessionId(hand: HandHistory | null | undefined, fallback?: string | null) {
  if (hand?.session_id) return hand.session_id;
  const metaSessionId = hand?.meta?.session_id;
  return typeof metaSessionId === "string" ? metaSessionId : fallback || undefined;
}

function replayPath(hand: HandHistory | null | undefined, fallbackSessionId?: string | null) {
  if (!hand?.hand_number) return "/replay";
  const sessionId = handSessionId(hand, fallbackSessionId);
  const query = sessionId ? `?session=${encodeURIComponent(sessionId)}` : "";
  return `/replay/${hand.hand_number}${query}`;
}

function formatPct(value?: number | null, digits = 1) {
  if (typeof value !== "number") return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatAction(action?: string | null) {
  return (action || "review").replace(/_/g, " ").toUpperCase();
}

export default function Session() {
  const { summary, refreshSummary } = useOutletContext<ShellContext>();
  const [session, setSession] = useState<GameSession | null>(null);
  const [handState, setHandState] = useState<GameHandState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingValue, setPendingValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const summaryMarkerRef = useRef<string | null>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);
  const [fallbackFullscreen, setFallbackFullscreen] = useState(false);

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
          localStorage.removeItem("ph_session_id");
          setSession(null);
          setHandState(null);
          setStatus(null);
          return;
        }
        setStatus(err instanceof Error ? err.message : "Failed to load session");
      });
  }, []);

  useEffect(() => {
    if (socket.state) {
      setHandState(socket.state);
      setStatus((current) => current?.startsWith("Gameplay started") ? null : current);
    }
  }, [socket.state]);

  useEffect(() => {
    if (!handState) return;
    if (!["hand_complete", "game_over", "tournament_complete"].includes(handState.status)) return;
    const marker = `${handState.status}:${handState.last_hand?.hand_number ?? ""}:${handState.terminal_reason ?? ""}`;
    if (summaryMarkerRef.current === marker) return;
    summaryMarkerRef.current = marker;
    refreshSummary?.();
  }, [handState?.last_hand?.hand_number, handState?.status, handState?.terminal_reason, refreshSummary]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const active = document.fullscreenElement === workspaceRef.current;
      setNativeFullscreen(active);
      if (!document.fullscreenElement) {
        setFallbackFullscreen(false);
      }
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    const node = workspaceRef.current;
    if (!node) return;

    if (fallbackFullscreen) {
      setFallbackFullscreen(false);
      return;
    }

    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        return;
      }
      if (typeof node.requestFullscreen === "function") {
        await node.requestFullscreen();
        setNativeFullscreen(true);
      } else {
        setFallbackFullscreen(true);
      }
    } catch {
      setFallbackFullscreen(true);
    }
  };

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
  const terminalReason = handState?.terminal_reason || gameState?.game_over_reason || session?.terminal_reason || null;
  const isTerminal = handState?.status === "game_over" || handState?.status === "tournament_complete" || Boolean(terminalReason);
  const displayedStatus = status?.startsWith("Gameplay started") && pending ? null : status;

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

  if (isTerminal) {
    actionContent = (
      <div className="module-intensity">
        Session ended{terminalReason ? `: ${terminalReason.replace(/_/g, " ")}` : "."}
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
  const lastHandReplayPath = replayPath(lastHand, session?.id);
  const liveCoach = handState?.live_coach || null;
  const fullscreenActive = nativeFullscreen || fallbackFullscreen;

  return (
    <section className="section session-page">
      <div
        ref={workspaceRef}
        data-testid="session-workspace"
        className={`session-workspace${fallbackFullscreen ? " is-fallback-fullscreen" : ""}`}
      >
        <div className="session-main">
          <div className="session-game-header">
            <div className="panel-header">
              <h2>Live Session</h2>
              <p>
                {session ? `Session ${session.id}` : "Create a session in the game lobby."}
                {session && (
                  <span className="session-socket-status">
                    {socket.status === "open" ? "WS live" : `WS ${socket.status}`}
                  </span>
                )}
              </p>
            </div>
            <button
              className="fullscreen-toggle"
              type="button"
              onClick={toggleFullscreen}
              aria-label={fullscreenActive ? "Exit fullscreen" : "Enter fullscreen"}
              title={fullscreenActive ? "Exit fullscreen" : "Enter fullscreen"}
            >
              <span className="fullscreen-glyph" aria-hidden="true" />
            </button>
          </div>

          {!session && (
            <Link className="btn primary session-lobby-link" to="/games">
              Open Game Lobby
            </Link>
          )}

          <div className="table-canvas session-table-canvas" data-testid="session-table-canvas">
            <NeonTable
              pot={gameState ? `$${gameState.pot_size?.toLocaleString?.() ?? gameState.pot_size ?? 0} POT` : undefined}
              action={gameState?.game_state}
              players={gameState?.players}
              heroCards={gameState?.hero_cards}
              communityCards={gameState?.community_cards}
            />
          </div>

          <div className="session-primary-actions">
            <button
              className="btn primary"
              type="button"
              onClick={() => startHand()}
              disabled={!session || submitting || Boolean(pending) || isTerminal}
            >
              {isTerminal
                ? "Session Over"
                : pending
                ? "Awaiting Action"
                : "Play Next Hand"}
            </button>
            {lastHandNumber ? (
              <Link className="btn ghost" to={lastHandReplayPath}>
                Review Last Hand
              </Link>
            ) : (
              <Link className="btn ghost" to="/replay">
                Open Replay Vault
              </Link>
            )}
          </div>
        </div>

        <aside className="session-rail" data-testid="session-rail">
          <div className="action-panel session-action-panel">
            <div className="panel-header">
              <h3>Action Console</h3>
              <p>{pending ? pending.prompt : "Start a hand to receive actions."}</p>
            </div>
            {actionContent}
            {(handState?.error || handState?.input_error || displayedStatus) && (
              <div className="form-status">
                {handState?.error || handState?.input_error || displayedStatus}
              </div>
            )}
          </div>

          <div className="coach-card live-coach-card">
            <div className="panel-header coach-card-header">
              <h3>Live Coach</h3>
              <p>{liveCoach ? liveCoach.summary : `Real-time feedback pipeline for ${summary.player.name}.`}</p>
            </div>
            {liveCoach ? (
              <>
                <div className="coach-recommendation">
                  <span>Recommended</span>
                  <strong>{formatAction(liveCoach.recommended_action)}</strong>
                  <span>{Math.round(liveCoach.confidence * 100)}% confidence</span>
                </div>
                <div className="coach-math-grid">
                  <div>
                    <span>Pot</span>
                    <strong>${liveCoach.math.pot}</strong>
                  </div>
                  <div>
                    <span>To call</span>
                    <strong>${liveCoach.math.to_call}</strong>
                  </div>
                  <div>
                    <span>Equity</span>
                    <strong>{formatPct(liveCoach.math.estimated_equity)}</strong>
                  </div>
                  <div>
                    <span>Required</span>
                    <strong>{formatPct(liveCoach.math.required_equity)}</strong>
                  </div>
                  <div>
                    <span>Edge</span>
                    <strong>{formatPct(liveCoach.math.equity_edge)}</strong>
                  </div>
                  <div>
                    <span>SPR</span>
                    <strong>{liveCoach.math.spr ?? "-"}</strong>
                  </div>
                </div>
                <ul className="coach-list">
                  {liveCoach.rationale.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                  {liveCoach.history_signals.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                  {liveCoach.warnings.map((item) => (
                    <li className="warn" key={item}>{item}</li>
                  ))}
                </ul>
                <div className="coach-card-actions">
                  {liveCoach.training_link && (
                    <Link className="btn ghost" to={liveCoach.training_link}>
                      Drill This Spot
                    </Link>
                  )}
                  <Link className="btn ghost" to="/training">
                    Training Plan
                  </Link>
                </div>
              </>
            ) : (
              <>
                <ul className="coach-list">
                  <li>Start a hand to receive action-specific math and history signals.</li>
                </ul>
                <Link className="btn ghost" to="/training">
                  Adjust Training Plan
                </Link>
              </>
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

          {/* Winner banner: prominent "you won/lost with..." card with
              the winning hand revealed. Sits above the coach-notes
              card so post-hand learning starts with the outcome. */}
          {handStatus === "hand_complete" && (
            <WinnerBanner hand={lastHand} heroName={gameState?.hero_name} />
          )}

          {lastHand?.coach_notes && handStatus === "hand_complete" && (
            <div className="coach-card">
              <div className="panel-header coach-card-header">
                <h3>
                  Coach notes - Hand grade{" "}
                  <span className={lastHand.coach_notes.hero_won ? "good" : "warn"}>
                    {lastHand.coach_notes.hand_grade}
                  </span>
                </h3>
                <p>{lastHand.coach_notes.headline}</p>
              </div>
              {lastHand.coach_notes.takeaway && (
                <div className="timeline-detail">{lastHand.coach_notes.takeaway}</div>
              )}
              {lastHand.coach_notes.worst_decision && (
                <div
                  className={`timeline-detail ${
                    lastHand.coach_notes.worst_decision.quality === "suboptimal" ? "warn" : ""
                  }`}
                >
                  Biggest leak: {lastHand.coach_notes.worst_decision.line}
                </div>
              )}
              {lastHand.coach_notes.gto_summary && (
                <div className="timeline-detail gto-summary">
                  <strong>GTO check:</strong>{" "}
                  <span>
                    Solver picks <em>{lastHand.coach_notes.gto_summary.gto_action}</em>
                    {typeof lastHand.coach_notes.gto_summary.gto_frequency === "number" &&
                      ` ${Math.round(
                        lastHand.coach_notes.gto_summary.gto_frequency * 100
                      )}% of the time`}
                    {lastHand.coach_notes.gto_summary.hero_action &&
                      lastHand.coach_notes.gto_summary.hero_action !==
                        lastHand.coach_notes.gto_summary.gto_action && (
                        <>
                          {" "}
                          - you picked{" "}
                          <em>{lastHand.coach_notes.gto_summary.hero_action}</em>
                          {typeof lastHand.coach_notes.gto_summary.hero_frequency === "number" &&
                            ` (GTO frequency ${Math.round(
                              lastHand.coach_notes.gto_summary.hero_frequency * 100
                            )}%)`}
                        </>
                      )}
                    {typeof lastHand.coach_notes.gto_summary.ev_delta_bb === "number" &&
                      lastHand.coach_notes.gto_summary.ev_delta_bb < 0 && (
                        <span className="warn">
                          {" "}
                          - estimated EV cost ~{lastHand.coach_notes.gto_summary.ev_delta_bb} BB
                        </span>
                      )}
                  </span>
                </div>
              )}
              {lastHandNumber && (
                <div className="coach-card-actions">
                  <Link className="btn ghost" to={lastHandReplayPath}>
                    Review full hand
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Action-by-action timeline grouped by street. Shows the
              full chip flow for every player (not just hero), so the
              user can audit the entire pot reconstruction. */}
          {handStatus === "hand_complete" && (
            <BetTimeline hand={lastHand} heroName={gameState?.hero_name} />
          )}

          {/* Per-decision bet breakdown. After every completed hand we
              show, for each tracked decision: street, action, chip
              amount, running pot. The user asked for this audit trail
              so a missed 38k-pot transfer would be immediately
              visible in the chip column. */}
          {lastHand?.decision_points && lastHand.decision_points.length > 0 && (
            <div className="coach-card bet-breakdown-card">
              <div className="panel-header coach-card-header">
                <h3>Bet breakdown</h3>
                <p>
                  Per-decision chip flow for hand #{lastHand.hand_number ?? "-"}.
                  Pot total: ${lastHand.pot_total ?? 0}.
                </p>
              </div>
              <table className="data-table bet-breakdown-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Street</th>
                    <th>Action</th>
                    <th>Amount</th>
                    <th>Pot before</th>
                    <th>Equity</th>
                    <th>Grade</th>
                  </tr>
                </thead>
                <tbody>
                  {lastHand.decision_points.map((d, idx) => {
                    const action = String(d.chosen_action ?? "?");
                    const amt = typeof d.chosen_amount === "number"
                      ? `$${d.chosen_amount.toLocaleString()}`
                      : "-";
                    const pot = typeof d.pot_total === "number"
                      ? `$${d.pot_total.toLocaleString()}`
                      : "-";
                    const eq = typeof d.equity === "number"
                      ? `${(d.equity * 100).toFixed(1)}%`
                      : "-";
                    const quality = String(d.quality ?? "ungraded");
                    const tone =
                      quality === "optimal"
                        ? "good"
                        : quality === "suboptimal" || quality === "mistake"
                          ? "warn"
                          : "";
                    return (
                      <tr key={idx}>
                        <td>{idx + 1}</td>
                        <td>{String(d.betting_round ?? "-")}</td>
                        <td>{action}</td>
                        <td>{amt}</td>
                        <td>{pot}</td>
                        <td>{eq}</td>
                        <td className={tone}>{quality}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

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
            <div className="hud-card">
              <div className="panel-header coach-card-header">
                <h3>HUD</h3>
                <p>Opponent profile (VPIP / PFR / AF)</p>
              </div>
              <table className="hud-table">
                <thead>
                  <tr>
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
                      <td>{opp.aggression_factor >= 99 ? "inf" : opp.aggression_factor.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {lastHand && (
            <div className="demo-hand last-hand-card">
              <div className="demo-row">
                <span>Last Hand</span>
                <span>{lastHandNumber ? <Link to={lastHandReplayPath}>#{lastHandNumber}</Link> : "-"}</span>
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
        </aside>
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import { getHandDetail, type HandHistory } from "../api/client";

export default function ReplayDetail() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const { handNumber } = useParams();
  const [hand, setHand] = useState<HandHistory | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const player = activePlayer || summary.player.name;
  const parsedHandNumber = Number(handNumber);
  const winningHandSummary = hand?.winning_hands
    ?.map((winningHand) => `${winningHand.player}: ${winningHand.rank ?? "Winning hand"}${winningHand.cards?.length ? ` (${winningHand.cards.join(" ")})` : ""}`)
    .join("; ");

  const formatPct = (value?: number) => {
    if (typeof value !== "number") return null;
    return `${(value * 100).toFixed(1)}%`;
  };

  useEffect(() => {
    if (!player || !Number.isInteger(parsedHandNumber)) {
      setStatus("Select a valid player and hand.");
      return;
    }

    getHandDetail(player, parsedHandNumber)
      .then((data) => {
        setHand(data);
        setStatus(null);
      })
      .catch((err) => {
        setHand(null);
        setStatus(err instanceof Error ? err.message : "Failed to load hand.");
      });
  }, [parsedHandNumber, player]);

  return (
    <>
      <section className="section">
        <div className="section-header">
          <div>
            <h2>Hand Replay</h2>
            <p>{hand ? `Hand ${hand.hand_number ?? parsedHandNumber}` : "Loading hand history."}</p>
          </div>
          <Link className="btn ghost" to="/replay">
            Back to Vault
          </Link>
        </div>

        {status && <div className="form-status">{status}</div>}

        {hand && (
          <div className="section split">
            <div className="panel">
              <div className="panel-header">
                <h2>Summary</h2>
                <p>{hand.started_at ?? "Recorded hand"}</p>
              </div>
              <div className="demo-hand">
                <div className="demo-row">
                  <span>Hero Cards</span>
                  <span>{hand.hero_hole_cards?.join(" ") || "-"}</span>
                </div>
                <div className="demo-row">
                  <span>Board</span>
                  <span>{hand.board?.join(" ") || "-"}</span>
                </div>
                <div className="demo-row">
                  <span>Winners</span>
                  <span>{hand.winners?.join(", ") || "-"}</span>
                </div>
                <div className="demo-row">
                  <span>Winning Hand</span>
                  <span>
                    {hand.won_by_fold
                      ? "Won by fold"
                      : winningHandSummary || hand.winning_hand_rank || "-"}
                  </span>
                </div>
                <div className="demo-row">
                  <span>Pot</span>
                  <span>${hand.pot_total ?? 0}</span>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2>Decision Grades</h2>
                <p>Captured coaching points for this hand.</p>
              </div>
              <div className="timeline">
                {(hand.decision_points ?? []).map((decision, index) => (
                  <div key={`${decision.betting_round ?? "street"}-${index}`} className="timeline-item">
                    <div className="timeline-time">{decision.betting_round ?? "hand"}</div>
                    <div className="timeline-body">
                      <div className="timeline-label">
                        {decision.chosen_action ?? "Action"} vs {decision.recommended_action ?? "recommendation"}
                      </div>
                      <div className="timeline-detail">
                        {decision.quality ?? "ungraded"}
                        {formatPct(decision.equity) && ` | equity ${formatPct(decision.equity)}`}
                        {formatPct(decision.required_equity) && ` | required ${formatPct(decision.required_equity)}`}
                      </div>
                      {typeof decision.analysis?.reasoning === "string" && (
                        <div className="timeline-detail">{decision.analysis.reasoning}</div>
                      )}
                      {decision.outs && Object.keys(decision.outs).length > 0 && (
                        <div className="timeline-detail">
                          Outs: {Object.entries(decision.outs).map(([key, value]) => {
                            if (typeof value === "object" && value && "outs" in value) {
                              return `${key} ${String(value.outs)}`;
                            }
                            return key;
                          }).join(", ")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {(!hand.decision_points || hand.decision_points.length === 0) && (
                  <div className="timeline-item">
                    <div className="timeline-time">-</div>
                    <div className="timeline-body">
                      <div className="timeline-label">No graded decisions</div>
                      <div className="timeline-detail">Play with training enabled to populate this area.</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {hand && (
        <section className="section">
          <div className="panel">
            <div className="panel-header">
              <h2>Action Log</h2>
              <p>Street-by-street betting history.</p>
            </div>
            <div className="timeline">
              {(hand.actions ?? []).map((action, index) => (
                <div key={`${action.player}-${action.betting_round}-${index}`} className="timeline-item">
                  <div className="timeline-time">{action.betting_round}</div>
                  <div className="timeline-body">
                    <div className="timeline-label">
                      {action.player} {action.action}
                      {action.amount ? ` $${action.amount}` : ""}
                    </div>
                    <div className="timeline-detail">
                      Pot ${action.pot_before} to ${action.pot_after}
                    </div>
                  </div>
                </div>
              ))}
              {(!hand.actions || hand.actions.length === 0) && (
                <div className="timeline-item">
                  <div className="timeline-time">-</div>
                  <div className="timeline-body">
                    <div className="timeline-label">No actions recorded</div>
                    <div className="timeline-detail">This hand record only contains summary data.</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </>
  );
}

import { useMemo } from "react";
import type { HandHistory } from "../api/client";

/**
 * Per-street action timeline for a completed hand.
 *
 * The backend's session_tracker captures every action with
 * ``{player, action, amount, pot_before, pot_after, betting_round}``
 * so we can reconstruct the full chip flow without a separate
 * snapshot table. This component groups those actions by street and
 * renders a compact log so users can audit:
 *
 *   - Who bet what, in what order, on each street.
 *   - How the pot grew action-by-action.
 *   - Where the raises landed and how much was added.
 *
 * Together with WinnerBanner and the existing decision_points table
 * this gives the full audit trail the user asked for ("clear output
 * showing the break down of the pot and each players bet amounts
 * each decision").
 */
type Props = {
  hand: HandHistory | null | undefined;
  heroName?: string;
};

const STREET_ORDER = ["preflop", "flop", "turn", "river"] as const;
type Street = (typeof STREET_ORDER)[number];

function formatAmount(amount: number): string {
  if (amount <= 0) return "—";
  return `$${amount.toLocaleString()}`;
}

function actionLabel(action: string): string {
  const a = action.toLowerCase();
  if (a === "check") return "checks";
  if (a === "call") return "calls";
  if (a === "fold") return "folds";
  if (a === "raise" || a === "bet") return "raises";
  if (a === "all_in" || a === "all-in") return "all-in";
  if (a === "small_blind") return "posts SB";
  if (a === "big_blind") return "posts BB";
  if (a === "ante") return "posts ante";
  return a;
}

function actionTone(action: string): string {
  const a = action.toLowerCase();
  if (a === "fold") return "muted";
  if (a === "raise" || a === "bet" || a === "all_in" || a === "all-in") return "warn";
  if (a === "check" || a === "call") return "";
  return "muted";
}

export default function BetTimeline({ hand, heroName }: Props) {
  const grouped = useMemo(() => {
    const byStreet: Record<Street, NonNullable<HandHistory["actions"]>> = {
      preflop: [],
      flop: [],
      turn: [],
      river: [],
    };
    for (const action of hand?.actions ?? []) {
      const street = String(action.betting_round || "").toLowerCase() as Street;
      if (street in byStreet) {
        byStreet[street].push(action);
      }
    }
    return byStreet;
  }, [hand?.actions]);

  if (!hand?.actions || hand.actions.length === 0) return null;

  return (
    <div className="coach-card bet-timeline-card">
      <div className="panel-header coach-card-header">
        <h3>Bet timeline</h3>
        <p>
          Action-by-action chip flow for hand #{hand.hand_number ?? "-"}.
          Each row shows who acted, how much went in, and the running pot.
        </p>
      </div>
      <div className="bet-timeline">
        {STREET_ORDER.map((street) => {
          const actions = grouped[street];
          if (actions.length === 0) return null;
          // Show the board cards available at this street for context.
          const boardCardsByStreet = hand.board_by_street as
            | Record<string, string[]>
            | undefined;
          const boardForStreet =
            boardCardsByStreet && boardCardsByStreet[street]
              ? boardCardsByStreet[street]
              : null;
          // Snapshot the pot at the start of the street (pot_before
          // of the first action on this street).
          const streetStartPot = actions[0]?.pot_before ?? 0;
          const streetEndPot = actions[actions.length - 1]?.pot_after ?? streetStartPot;
          return (
            <div key={street} className="bet-timeline-street">
              <div className="bet-timeline-street-header">
                <span className="bet-timeline-street-label">{street}</span>
                {boardForStreet && (
                  <span className="bet-timeline-board muted small">
                    Board: {boardForStreet.join(" ")}
                  </span>
                )}
                <span className="bet-timeline-pot muted small">
                  Pot: ${streetStartPot.toLocaleString()} → ${streetEndPot.toLocaleString()}
                </span>
              </div>
              <ol className="bet-timeline-actions">
                {actions.map((action, idx) => {
                  const isHero = heroName !== undefined && action.player === heroName;
                  return (
                    <li
                      key={`${street}-${idx}`}
                      className={`bet-timeline-action ${isHero ? "hero" : ""}`}
                    >
                      <span className="bet-timeline-player">{action.player}</span>{" "}
                      <span className={`bet-timeline-verb ${actionTone(action.action)}`}>
                        {actionLabel(action.action)}
                      </span>{" "}
                      <span className="bet-timeline-amount">
                        {formatAmount(action.amount)}
                      </span>{" "}
                      <span className="muted small">
                        (pot ${action.pot_after.toLocaleString()})
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>
          );
        })}
      </div>
    </div>
  );
}

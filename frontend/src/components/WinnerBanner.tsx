import type { HandHistory, WinningHand } from "../api/client";

/**
 * Post-hand "Hero wins / Villain wins with..." banner with winning
 * cards revealed.
 *
 * Why a dedicated component: ``coach_notes.headline`` carries the
 * outcome as a plain sentence, but learners benefit from a visual
 * board + hole-card display that mirrors what they'd see at a real
 * table. The banner pulls ``hand.winning_hands[]`` (already persisted
 * by ``_build_winning_hand_details``) and renders the actual 5 cards
 * that made the winning hand, plus the rank label (e.g. "Two Pair").
 *
 * Renders nothing when the hand isn't complete or no winners are
 * recorded; the caller can drop it next to any other post-hand
 * card without conditional logic.
 */
type Props = {
  hand: HandHistory | null | undefined;
  heroName?: string;
};

function suitSymbol(card: string): { symbol: string; tone: string } {
  // Cards arrive as e.g. "A♠" / "K♥" / "10♣" / "Qs" / "Th".
  // Extract the suit (last char) and map to a CSS tone class.
  const c = card.trim();
  const last = c.charAt(c.length - 1);
  if (last === "♠" || last === "S" || last === "s") return { symbol: "♠", tone: "spade" };
  if (last === "♥" || last === "H" || last === "h") return { symbol: "♥", tone: "heart" };
  if (last === "♦" || last === "D" || last === "d") return { symbol: "♦", tone: "diamond" };
  if (last === "♣" || last === "C" || last === "c") return { symbol: "♣", tone: "club" };
  return { symbol: "?", tone: "unknown" };
}

function cardRank(card: string): string {
  const c = card.trim();
  // Everything before the suit char.
  return c.slice(0, c.length - 1) || "?";
}

function CardFace({ card }: { card: string }) {
  const { symbol, tone } = suitSymbol(card);
  return (
    <div className={`winner-card-face winner-card-${tone}`} title={card}>
      <span className="winner-card-rank">{cardRank(card)}</span>
      <span className="winner-card-suit">{symbol}</span>
    </div>
  );
}

function WinningHandRow({ entry, isHero }: { entry: WinningHand; isHero: boolean }) {
  const cards = entry.cards ?? [];
  const hole = entry.hole_cards ?? [];
  return (
    <div className={`winner-row ${isHero ? "winner-row-hero" : ""}`}>
      <div className="winner-row-header">
        <span className="winner-player">{entry.player}</span>
        {entry.rank && <span className="winner-rank">{entry.rank}</span>}
        {isHero && <span className="winner-tag good">YOU</span>}
      </div>
      <div className="winner-cards">
        {cards.map((c, i) => (
          <CardFace key={`best-${i}-${c}`} card={c} />
        ))}
      </div>
      {hole.length > 0 && (
        <div className="winner-hole">
          <span className="muted small">Hole: </span>
          {hole.map((c, i) => (
            <CardFace key={`hole-${i}-${c}`} card={c} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function WinnerBanner({ hand, heroName }: Props) {
  if (!hand) return null;
  const winners = hand.winners ?? [];
  if (winners.length === 0) return null;

  const winningHands = hand.winning_hands ?? [];
  const wonByFold = Boolean(hand.won_by_fold);
  const potTotal = hand.pot_total ?? 0;

  // Find the hero's place in the result.
  const heroWon = heroName ? winners.includes(heroName) : false;
  const bannerTone = heroWon ? "good" : "warn";
  const outcomeText = heroWon
    ? `You won $${potTotal.toLocaleString()}`
    : `${winners.join(", ")} won $${potTotal.toLocaleString()}`;

  return (
    <div className={`winner-banner ${bannerTone}`}>
      <div className="winner-banner-header">
        <div className="winner-banner-title">{outcomeText}</div>
        {wonByFold ? (
          <div className="winner-banner-sub">Won by fold — opponents declined.</div>
        ) : winningHands.length > 0 ? (
          <div className="winner-banner-sub">
            {winningHands.length > 1
              ? `Split pot ${winningHands.length} ways at showdown.`
              : `Won at showdown with ${winningHands[0].rank ?? "the best hand"}.`}
          </div>
        ) : (
          <div className="winner-banner-sub">Hand complete.</div>
        )}
      </div>
      {!wonByFold && winningHands.length > 0 && (
        <div className="winner-hands">
          {winningHands.map((entry, i) => (
            <WinningHandRow
              key={`${entry.player}-${i}`}
              entry={entry}
              isHero={heroName !== undefined && entry.player === heroName}
            />
          ))}
        </div>
      )}
    </div>
  );
}

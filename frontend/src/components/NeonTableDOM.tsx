/**
 * Pure DOM/CSS poker table.
 *
 * The render path is intentionally DOM-first: no GPU dependency, stable
 * under React StrictMode, and readable by browser accessibility tooling.
 * It keeps the public NeonTable prop shape used by Home and Session.
 */
import { useMemo } from "react";

export interface PlayerSeatState {
  name: string;
  bankroll: number;
  current_bet: number;
  folded: boolean;
  all_in: boolean;
  isHero?: boolean;
  is_hero?: boolean;
  is_dealer?: boolean;
  is_small_blind?: boolean;
  is_big_blind?: boolean;
}

export interface NeonTableDOMProps {
  pot?: string;
  action?: string;
  players?: PlayerSeatState[];
  heroCards?: string[];
  communityCards?: string[];
}

type SuitKey = "h" | "d" | "c" | "s" | "unknown";

interface SuitMeta {
  symbol: string;
  tone: string;
  label: string;
}

const SUITS: Record<SuitKey, SuitMeta> = {
  h: { symbol: "♥", tone: "heart", label: "Hearts" },
  d: { symbol: "♦", tone: "diamond", label: "Diamonds" },
  c: { symbol: "♣", tone: "club", label: "Clubs" },
  s: { symbol: "♠", tone: "spade", label: "Spades" },
  unknown: { symbol: "?", tone: "unknown", label: "Unknown" },
};

function parseCard(card: string): { rank: string; suit: SuitMeta } {
  if (!card) return { rank: "?", suit: SUITS.unknown };
  const cleaned = card.trim();
  const last = cleaned.charAt(cleaned.length - 1);
  let suitKey: SuitKey = "unknown";
  if (last === "♥" || last === "H" || last === "h") suitKey = "h";
  else if (last === "♦" || last === "D" || last === "d") suitKey = "d";
  else if (last === "♣" || last === "C" || last === "c") suitKey = "c";
  else if (last === "♠" || last === "S" || last === "s") suitKey = "s";
  const rank = cleaned.slice(0, cleaned.length - 1) || "?";
  return { rank, suit: SUITS[suitKey] };
}

function CardFace({ card, faceDown }: { card?: string | null; faceDown?: boolean }) {
  if (faceDown || !card) {
    return <div className="dom-card dom-card-back" aria-label="Face-down card" />;
  }
  const { rank, suit } = parseCard(card);
  return (
    <div
      className={`dom-card dom-card-${suit.tone}`}
      aria-label={`${rank} of ${suit.label}`}
    >
      <span className="dom-card-rank">{rank}</span>
      <span className="dom-card-suit">{suit.symbol}</span>
    </div>
  );
}

function ChipStack({ amount }: { amount: number }) {
  if (!amount || amount <= 0) return null;
  // Render a tiny chip icon + the chip value. We don't try to model
  // individual chip denominations; one chip + label is enough to
  // convey "money is in play".
  return (
    <div className="dom-chip-stack" title={`Bet: ${amount.toLocaleString()}`}>
      <div className="dom-chip" />
      <div className="dom-chip-amount">${amount.toLocaleString()}</div>
    </div>
  );
}

function roleBadges(player: PlayerSeatState) {
  // Dealer button is mutually exclusive with SB/BB labels in 2+ player
  // games (the dealer can also be SB heads-up, but the engine separates
  // those concepts via is_dealer + is_small_blind). Render whichever
  // chips are flagged; the order is intentional D | SB | BB.
  const badges: Array<{ label: string; tone: string }> = [];
  if (player.is_dealer) badges.push({ label: "D", tone: "dealer" });
  if (player.is_small_blind) badges.push({ label: "SB", tone: "sb" });
  if (player.is_big_blind) badges.push({ label: "BB", tone: "bb" });
  if (badges.length === 0) return null;
  return (
    <div className="dom-role-badges">
      {badges.map((b) => (
        <span key={b.label} className={`dom-role-chip dom-role-${b.tone}`}>
          {b.label}
        </span>
      ))}
    </div>
  );
}

function isHeroSeat(player: PlayerSeatState): boolean {
  return Boolean(player.isHero || player.is_hero);
}

/**
 * Compute the (top%, left%) position for a seat index given a player
 * count. We place hero (always seat 0 in our ordering) at the
 * bottom-center, then distribute the remaining seats evenly around
 * the oval clockwise so dealer/blind movement matches poker action.
 */
function seatPosition(
  seatIndex: number,
  seatCount: number
): { topPct: number; leftPct: number } {
  if (seatCount <= 0) return { topPct: 50, leftPct: 50 };
  // angle in degrees, where 90 = bottom (hero), measured clockwise in CSS space.
  const angleDeg = 90 + (seatIndex * 360) / seatCount;
  const angleRad = (angleDeg * Math.PI) / 180;
  // The oval seat ring sits just outside the felt. These radii are
  // percent-based so the table scales fluidly with the container.
  const rx = 43; // horizontal radius %
  const ry = 39; // vertical radius %
  const cx = 50;
  const cy = 50;
  const leftPct = cx + rx * Math.cos(angleRad);
  // CSS Y grows down, so positive sine places seats lower on the table.
  const topPct = cy + ry * Math.sin(angleRad);
  return { topPct, leftPct };
}

function Seat({
  player,
  position,
}: {
  player: PlayerSeatState;
  position: { topPct: number; leftPct: number };
}) {
  const status = player.folded
    ? "FOLDED"
    : player.all_in
      ? "ALL-IN"
      : player.current_bet > 0
        ? `BET $${player.current_bet.toLocaleString()}`
        : "READY";
  const tone = player.folded
    ? "folded"
    : player.all_in
      ? "all-in"
      : isHeroSeat(player)
        ? "hero"
        : "live";

  return (
    <div
      className={`dom-seat dom-seat-${tone}`}
      style={{
        top: `${position.topPct}%`,
        left: `${position.leftPct}%`,
      }}
    >
      <div className="dom-seat-panel">
        <div className="dom-seat-header">
          <span className="dom-seat-name">{player.name || "Player"}</span>
          {roleBadges(player)}
        </div>
        <div className="dom-seat-stack">${player.bankroll.toLocaleString()}</div>
        <div className={`dom-seat-status dom-status-${tone}`}>{status}</div>
      </div>
      {/*
        Bet chips are positioned slightly toward the felt center so
        they visually "move into" the pot. We use a child div with
        absolute positioning relative to the seat panel.
      */}
      <ChipStack amount={player.current_bet} />
    </div>
  );
}

export default function NeonTableDOM({
  pot = "$0 POT",
  action = "Waiting...",
  players = [],
  heroCards = [],
  communityCards = [],
}: NeonTableDOMProps) {
  // Reorder players so the hero is always at seat 0 (bottom-center).
  // If no player is flagged as hero, we still render in the given order.
  const orderedPlayers = useMemo(() => {
    if (players.length === 0) return players;
    const heroIdx = players.findIndex(isHeroSeat);
    if (heroIdx <= 0) return players;
    return [
      players[heroIdx],
      ...players.slice(heroIdx + 1),
      ...players.slice(0, heroIdx),
    ];
  }, [players]);

  // Community cards: always render 5 slots so the spacing stays the
  // same as cards reveal across streets.
  const communitySlots = useMemo(() => {
    const slots: Array<string | null> = Array(5).fill(null);
    for (let i = 0; i < Math.min(5, communityCards.length); i++) {
      slots[i] = communityCards[i];
    }
    return slots;
  }, [communityCards]);

  // Hero cards default to two face-down placeholders if not provided.
  const heroSlots: Array<string | null> = [
    heroCards[0] ?? null,
    heroCards[1] ?? null,
  ];

  return (
    <div className="dom-table-frame">
      {/* Outer felt + neon ring */}
      <div className="dom-table-felt">
        <div className="dom-table-ring" />
        <div className="dom-table-inner-ring" />

        {/* Center: pot + action label + community cards */}
        <div className="dom-table-center">
          <div className="dom-community-row">
            {communitySlots.map((card, i) => (
              <CardFace key={`community-${i}`} card={card} faceDown={!card} />
            ))}
          </div>
          <div className="dom-pot-readout">{pot}</div>
          <div className="dom-action-readout">{action}</div>
        </div>

        {/* Player seats around the felt */}
        {orderedPlayers.map((player, idx) => {
          const pos = seatPosition(idx, orderedPlayers.length);
          return (
            <Seat
              key={`${player.name}-${idx}`}
              player={player}
              position={pos}
            />
          );
        })}

        {/* Hero hole cards: rendered as their own row centered at the
            bottom, just above the hero seat panel. Only visible if
            there's a hero in the ordered players list. */}
        {orderedPlayers.some(isHeroSeat) && (
          <div className="dom-hero-cards">
            <CardFace card={heroSlots[0]} faceDown={!heroSlots[0]} />
            <CardFace card={heroSlots[1]} faceDown={!heroSlots[1]} />
          </div>
        )}
      </div>
    </div>
  );
}

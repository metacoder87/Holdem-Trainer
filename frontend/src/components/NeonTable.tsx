import { Container, Graphics, Stage, Text, useTick } from "@pixi/react";
import { BlurFilter, TextStyle } from "pixi.js";
import { useCallback, useMemo, useRef } from "react";
import type { Container as PixiContainer, Graphics as PixiGraphics } from "pixi.js";
import type { LiveGameState } from "../api/client";

const TABLE_SIZE = 360;
const CENTER = TABLE_SIZE / 2;
const OUTER_RADIUS = 150;
const INNER_RADIUS = 110;
const CARD_WIDTH = 34;
const CARD_HEIGHT = 48;
const SUIT_COLORS: Record<string, number> = {
  h: 0xff5c6c,
  d: 0xff5c6c,
  s: 0xe7f0ff,
  c: 0xe7f0ff
};

const FALLBACK_BOARD_SLOTS = 5;

export type NeonTableProps = {
  liveState?: LiveGameState | null;
  heroName?: string | null;
};

type SeatLayout = { label: string; angle: number };

function buildSeatLayout(state: LiveGameState | null | undefined, heroName: string | null | undefined): SeatLayout[] {
  if (!state || !state.players || state.players.length === 0) {
    return [
      { label: "Coach Bot", angle: -90 },
      { label: "Aggro AI", angle: -30 },
      { label: "Balanced AI", angle: 30 },
      { label: "Hero", angle: 90 },
      { label: "Tight AI", angle: 150 },
      { label: "Wild AI", angle: -150 }
    ];
  }

  const heroIndex = state.players.findIndex(
    (player) => player.name === (heroName ?? state.hero_name)
  );

  const ordered = heroIndex >= 0
    ? [...state.players.slice(heroIndex), ...state.players.slice(0, heroIndex)]
    : state.players;

  const count = ordered.length;
  return ordered.map((player, index) => {
    // Hero anchored to seat at angle 90 (bottom), others spread evenly.
    const angle = 90 + (index / count) * 360;
    const normalized = ((angle + 180) % 360) - 180;
    return {
      label: player.folded
        ? `${player.name} (folded)`
        : player.all_in
        ? `${player.name} (all-in)`
        : `${player.name} ${player.bankroll}`,
      angle: normalized
    };
  });
}

function parseCardSuit(card: string): number {
  if (!card || card.length < 2) return 0xb7c6da;
  return SUIT_COLORS[card.slice(-1).toLowerCase()] ?? 0xb7c6da;
}

function buildBoardSlots(board: string[] | undefined) {
  const xs = [-52, -26, 0, 26, 52];
  return xs.map((x, index) => ({ id: `c${index + 1}`, x, y: -42, card: board?.[index] }));
}

function buildHeroSlots(heroCards: string[] | undefined) {
  const xs = [-22, 22];
  return xs.map((x, index) => ({ id: `h${index + 1}`, x, y: 62, card: heroCards?.[index] }));
}

function TableScene({ liveState, heroName }: NeonTableProps) {
  const ringRef = useRef<PixiContainer>(null);
  const pulseRef = useRef<PixiGraphics>(null);
  const pulse = useRef(0);

  const seats = useMemo(() => buildSeatLayout(liveState ?? null, heroName), [liveState, heroName]);
  const boardSlots = useMemo(() => buildBoardSlots(liveState?.community_cards), [liveState?.community_cards]);
  const heroSlots = useMemo(() => buildHeroSlots(liveState?.hero_cards), [liveState?.hero_cards]);

  useTick((delta) => {
    if (ringRef.current) {
      ringRef.current.rotation += 0.0025 * delta;
    }
    if (pulseRef.current) {
      pulse.current += 0.02 * delta;
      pulseRef.current.alpha = 0.35 + Math.sin(pulse.current) * 0.15;
    }
  });

  const drawTable = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x0b1018, 0.95);
    graphics.drawCircle(0, 0, OUTER_RADIUS);
    graphics.endFill();

    graphics.beginFill(0x0f1a24, 0.95);
    graphics.drawCircle(0, 0, INNER_RADIUS);
    graphics.endFill();
  }, []);

  const drawGlow = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.lineStyle(2, 0x28f4ff, 0.5);
    graphics.drawCircle(0, 0, OUTER_RADIUS + 6);
  }, []);

  const drawOrbit = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.lineStyle(1, 0x7dff8a, 0.45);
    graphics.drawCircle(0, 0, OUTER_RADIUS - 22);
  }, []);

  const drawCardBack = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x111a27, 0.9);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, 6);
    graphics.endFill();
    graphics.lineStyle(1, 0x4d77ff, 0.6);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, 6);
  }, []);

  const drawCardFront = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x0f1a24, 0.95);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, 6);
    graphics.endFill();
    graphics.lineStyle(1, 0x28f4ff, 0.65);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, 6);
  }, []);

  const seatStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk",
        fontSize: 11,
        fill: 0xb7c6da
      }),
    []
  );

  const centerLabel = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron",
        fontSize: 12,
        fill: 0x7b8ba3,
        letterSpacing: 3,
        align: "center"
      }),
    []
  );

  const centerPot = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron",
        fontSize: 20,
        fill: 0x28f4ff,
        align: "center"
      }),
    []
  );

  const centerAction = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk",
        fontSize: 12,
        fill: 0xb7c6da,
        align: "center"
      }),
    []
  );

  const cardTextStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk",
        fontSize: 14,
        fill: 0xe7f0ff,
        fontWeight: "bold"
      }),
    []
  );

  const glowFilter = useMemo(() => [new BlurFilter(8)], []);

  const potLabel = liveState?.pot_size != null ? `$${liveState.pot_size.toLocaleString()}` : "-";
  const phaseLabel = liveState?.game_state ? liveState.game_state.toUpperCase() : "WAITING";

  return (
    <Container x={CENTER} y={CENTER}>
      <Graphics draw={drawTable} />
      <Graphics draw={drawGlow} filters={glowFilter} ref={pulseRef} />
      <Container ref={ringRef}>
        <Graphics draw={drawOrbit} />
      </Container>

      <Text text="LIVE TABLE" anchor={0.5} y={-18} style={centerLabel} />
      <Text text={potLabel} anchor={0.5} y={4} style={centerPot} />
      <Text text={phaseLabel} anchor={0.5} y={28} style={centerAction} />

      {boardSlots.map((slot, index) => {
        const card = slot.card;
        return (
          <Container key={slot.id} x={slot.x} y={slot.y}>
            {card ? (
              <>
                <Graphics draw={drawCardFront} />
                <Text
                  text={card}
                  anchor={0.5}
                  style={
                    new TextStyle({
                      ...cardTextStyle,
                      fill: parseCardSuit(card)
                    })
                  }
                />
              </>
            ) : index < FALLBACK_BOARD_SLOTS && !liveState ? (
              <Graphics draw={drawCardBack} alpha={0.3} />
            ) : null}
          </Container>
        );
      })}

      {heroSlots.map((slot) => {
        const card = slot.card;
        return (
          <Container key={slot.id} x={slot.x} y={slot.y}>
            {card ? (
              <>
                <Graphics draw={drawCardFront} />
                <Text
                  text={card}
                  anchor={0.5}
                  style={
                    new TextStyle({
                      ...cardTextStyle,
                      fill: parseCardSuit(card)
                    })
                  }
                />
              </>
            ) : (
              <Graphics draw={drawCardBack} alpha={0.5} />
            )}
          </Container>
        );
      })}

      {seats.map((seat) => {
        const angle = (seat.angle * Math.PI) / 180;
        const radius = OUTER_RADIUS - 6;
        return (
          <Text
            key={seat.label}
            text={seat.label}
            anchor={0.5}
            x={Math.cos(angle) * radius}
            y={Math.sin(angle) * radius}
            style={seatStyle}
          />
        );
      })}
    </Container>
  );
}

export default function NeonTable({ liveState, heroName }: NeonTableProps = {}) {
  const devicePixelRatio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;

  return (
    <Stage
      width={TABLE_SIZE}
      height={TABLE_SIZE}
      options={{
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: devicePixelRatio
      }}
    >
      <TableScene liveState={liveState} heroName={heroName} />
    </Stage>
  );
}

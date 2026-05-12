import { Container, Graphics, Stage, Text, useTick } from "@pixi/react";
import { BlurFilter, TextStyle } from "pixi.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Container as PixiContainer, Graphics as PixiGraphics } from "pixi.js";

const TABLE_WIDTH = 900;
const TABLE_HEIGHT = 560;
const CENTER_X = TABLE_WIDTH / 2;
const CENTER_Y = TABLE_HEIGHT / 2;
const TABLE_RX = 342;
const TABLE_RY = 176;
const INNER_RX = 266;
const INNER_RY = 116;
const SEAT_RX = TABLE_RX + 54;
const SEAT_RY = TABLE_RY + 48;
const CARD_RX = TABLE_RX - 84;
const CARD_RY = TABLE_RY - 48;
const CARD_WIDTH = 58;
const CARD_HEIGHT = 78;
const CARD_RADIUS = 9;
const CARD_TEXT = 0xf0eadf;

type SuitKey = "h" | "d" | "c" | "s" | "unknown";

interface PlayerState {
  name: string;
  bankroll: number;
  current_bet: number;
  folded: boolean;
  all_in: boolean;
  isHero?: boolean;
}

interface NeonTableProps {
  pot?: string;
  action?: string;
  seats?: Array<{ label: string; angle: number }>;
  players?: PlayerState[];
  heroCards?: string[];
  communityCards?: string[];
}

interface SuitMeta {
  key: SuitKey;
  symbol: string;
  color: number;
  glow: string;
  label: string;
}

interface ParsedCard {
  raw: string;
  rank: string;
  suit: SuitMeta;
}

const UNKNOWN_SUIT: SuitMeta = {
  key: "unknown",
  symbol: "?",
  color: 0xcadfed,
  glow: "#cadfed",
  label: "Unknown"
};

const SUITS: Record<SuitKey, SuitMeta> = {
  h: { key: "h", symbol: "\u2665", color: 0xd97885, glow: "#d97885", label: "Hearts" },
  d: { key: "d", symbol: "\u2666", color: 0x78cfd9, glow: "#78cfd9", label: "Diamonds" },
  c: { key: "c", symbol: "\u2663", color: 0x82d69a, glow: "#82d69a", label: "Clubs" },
  s: { key: "s", symbol: "\u2660", color: 0xa99bd6, glow: "#a99bd6", label: "Spades" },
  unknown: UNKNOWN_SUIT
};

const SUIT_TOKENS: Array<[string, SuitKey]> = [
  ["\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a5", "h"],
  ["\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a6", "d"],
  ["\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a3", "c"],
  ["\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a0", "s"],
  ["\u00e2\u2122\u00a5", "h"],
  ["\u00e2\u2122\u00a6", "d"],
  ["\u00e2\u2122\u00a3", "c"],
  ["\u00e2\u2122\u00a0", "s"],
  ["\u2665", "h"],
  ["\u2666", "d"],
  ["\u2663", "c"],
  ["\u2660", "s"],
  ["H", "h"],
  ["D", "d"],
  ["C", "c"],
  ["S", "s"],
  ["h", "h"],
  ["d", "d"],
  ["c", "c"],
  ["s", "s"]
];

const FALLBACK_PLAYERS: PlayerState[] = [
  { name: "Hero", bankroll: 1000, current_bet: 0, folded: false, all_in: false, isHero: true },
  { name: "Villain", bankroll: 1000, current_bet: 0, folded: false, all_in: false }
];

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);

    const updatePreference = () => setReducedMotion(media.matches);
    media.addEventListener?.("change", updatePreference);
    return () => media.removeEventListener?.("change", updatePreference);
  }, []);

  return reducedMotion;
}

function normalizeCardText(card: string) {
  return String(card || "")
    .trim()
    .replace(/\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a5/g, "\u2665")
    .replace(/\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a6/g, "\u2666")
    .replace(/\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a3/g, "\u2663")
    .replace(/\u00c3\u00a2\u00e2\u201e\u00a2\u00c2\u00a0/g, "\u2660")
    .replace(/\u00e2\u2122\u00a5/g, "\u2665")
    .replace(/\u00e2\u2122\u00a6/g, "\u2666")
    .replace(/\u00e2\u2122\u00a3/g, "\u2663")
    .replace(/\u00e2\u2122\u00a0/g, "\u2660");
}

function parseCard(cardStr: string): ParsedCard {
  const raw = normalizeCardText(cardStr);
  if (!raw) {
    return { raw: cardStr, rank: "?", suit: UNKNOWN_SUIT };
  }

  for (const [token, key] of SUIT_TOKENS) {
    if (raw.endsWith(token)) {
      const rankRaw = raw.slice(0, -token.length).trim().toUpperCase();
      const rank = rankRaw === "T" ? "10" : rankRaw || "?";
      return { raw: cardStr, rank, suit: SUITS[key] };
    }
  }

  const rank = raw.slice(0, -1).trim().toUpperCase() || raw.toUpperCase();
  return { raw: cardStr, rank: rank === "T" ? "10" : rank, suit: UNKNOWN_SUIT };
}

function easeOut(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

function clamp(value: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function formatStack(amount: number) {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(amount % 1000 === 0 ? 0 : 1)}k`;
  }
  return `$${amount}`;
}

function ellipsePoint(angleDeg: number, rx: number, ry: number) {
  const angle = (angleDeg * Math.PI) / 180;
  return {
    x: Math.cos(angle) * rx,
    y: Math.sin(angle) * ry
  };
}

function compactName(name: string) {
  if (name.length <= 12) {
    return name;
  }
  return `${name.slice(0, 10)}...`;
}

function PlayingCard({
  card,
  x = 0,
  y = 0,
  rotation = 0,
  delay = 0,
  faceDown = false,
  reducedMotion = false,
  compact = false
}: {
  card?: ParsedCard;
  x?: number;
  y?: number;
  rotation?: number;
  delay?: number;
  faceDown?: boolean;
  reducedMotion?: boolean;
  compact?: boolean;
}) {
  const containerRef = useRef<PixiContainer>(null);
  const animationProgress = useRef(reducedMotion ? 1 : -delay);
  const drift = useRef(0);

  const parsed = card ?? { raw: "", rank: "?", suit: UNKNOWN_SUIT };
  const width = compact ? CARD_WIDTH - 8 : CARD_WIDTH;
  const height = compact ? CARD_HEIGHT - 10 : CARD_HEIGHT;
  const cornerOffsetX = -width / 2 + 7;
  const cornerOffsetY = -height / 2 + 7;

  useEffect(() => {
    animationProgress.current = reducedMotion ? 1 : -delay;
  }, [parsed.raw, faceDown, reducedMotion, delay]);

  useTick((delta) => {
    const node = containerRef.current;
    if (!node) {
      return;
    }

    if (reducedMotion) {
      node.alpha = faceDown ? 0.84 : 1;
      node.y = y;
      node.scale.set(1);
      return;
    }

    animationProgress.current = Math.min(1, animationProgress.current + 0.065 * delta);
    drift.current += 0.014 * delta;
    const visibleProgress = clamp(animationProgress.current);
    const eased = easeOut(visibleProgress);
    node.alpha = 0.08 + visibleProgress * 0.92;
    node.y = y - (1 - visibleProgress) * 12 + Math.sin(drift.current + delay * 8) * 0.45;
    node.scale.set(0.92 + eased * 0.08);
  });

  const drawFace = useCallback(
    (graphics: PixiGraphics) => {
      graphics.clear();
      graphics.beginFill(0x111927, 0.96);
      graphics.drawRoundedRect(-width / 2, -height / 2, width, height, CARD_RADIUS);
      graphics.endFill();

      graphics.beginFill(0xf0eadf, 0.045);
      graphics.drawRoundedRect(-width / 2 + 4, -height / 2 + 4, width - 8, height - 8, CARD_RADIUS - 3);
      graphics.endFill();

      graphics.lineStyle(1.5, parsed.suit.color, 0.58);
      graphics.drawRoundedRect(-width / 2, -height / 2, width, height, CARD_RADIUS);
      graphics.lineStyle(1, 0xf0eadf, 0.13);
      graphics.drawRoundedRect(-width / 2 + 5, -height / 2 + 5, width - 10, height - 10, CARD_RADIUS - 4);

      graphics.beginFill(parsed.suit.color, 0.08);
      graphics.drawCircle(width / 2 - 10, -height / 2 + 10, 14);
      graphics.drawCircle(-width / 2 + 12, height / 2 - 12, 10);
      graphics.endFill();
    },
    [height, parsed.suit.color, width]
  );

  const drawBack = useCallback(
    (graphics: PixiGraphics) => {
      graphics.clear();
      graphics.beginFill(0x0d1624, 0.96);
      graphics.drawRoundedRect(-width / 2, -height / 2, width, height, CARD_RADIUS);
      graphics.endFill();

      graphics.beginFill(0x78cfd9, 0.05);
      graphics.drawRoundedRect(-width / 2 + 4, -height / 2 + 4, width - 8, height - 8, CARD_RADIUS - 3);
      graphics.endFill();

      graphics.lineStyle(1.5, 0x78cfd9, 0.42);
      graphics.drawRoundedRect(-width / 2, -height / 2, width, height, CARD_RADIUS);
      graphics.lineStyle(1, 0x82d69a, 0.2);
      graphics.drawRoundedRect(-width / 2 + 6, -height / 2 + 6, width - 12, height - 12, CARD_RADIUS - 4);

      graphics.lineStyle(1, 0x78cfd9, 0.26);
      graphics.moveTo(-width / 2 + 13, -height / 2 + 18);
      graphics.lineTo(-5, -height / 2 + 18);
      graphics.lineTo(-5, -8);
      graphics.moveTo(width / 2 - 13, height / 2 - 18);
      graphics.lineTo(6, height / 2 - 18);
      graphics.lineTo(6, 9);
      graphics.moveTo(-width / 2 + 11, height / 2 - 15);
      graphics.lineTo(-width / 2 + 24, height / 2 - 15);
      graphics.lineTo(-width / 2 + 24, 12);
      graphics.moveTo(width / 2 - 11, -height / 2 + 15);
      graphics.lineTo(width / 2 - 24, -height / 2 + 15);
      graphics.lineTo(width / 2 - 24, -10);

      graphics.beginFill(0x78cfd9, 0.34);
      graphics.drawCircle(0, 0, compact ? 7 : 9);
      graphics.endFill();
      graphics.beginFill(0xf0eadf, 0.34);
      graphics.drawCircle(0, 0, compact ? 2.5 : 3.5);
      graphics.endFill();
    },
    [compact, height, width]
  );

  const cornerStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, Segoe UI, sans-serif",
        fontSize: compact ? 9 : 11,
        fontWeight: "700",
        fill: CARD_TEXT,
        dropShadow: true,
        dropShadowColor: "#000000",
        dropShadowBlur: 2,
        dropShadowDistance: 1
      }),
    [compact]
  );

  const suitStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Georgia, Times New Roman, serif",
        fontSize: compact ? 28 : 35,
        fontWeight: "700",
        fill: parsed.suit.color,
        align: "center",
        dropShadow: true,
        dropShadowColor: parsed.suit.glow,
        dropShadowBlur: 3,
        dropShadowDistance: 0
      }),
    [compact, parsed.suit.color, parsed.suit.glow]
  );

  const smallSuitStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Georgia, Times New Roman, serif",
        fontSize: compact ? 10 : 12,
        fontWeight: "700",
        fill: parsed.suit.color
      }),
    [compact, parsed.suit.color]
  );

  return (
    <Container ref={containerRef} x={x} y={y} rotation={rotation}>
      {faceDown ? (
        <Graphics draw={drawBack} />
      ) : (
        <>
          <Graphics draw={drawFace} />
          <Text text={parsed.rank} x={cornerOffsetX} y={cornerOffsetY} style={cornerStyle} />
          <Text text={parsed.suit.symbol} x={cornerOffsetX + 1} y={cornerOffsetY + 13} style={smallSuitStyle} />
          <Text text={parsed.suit.symbol} anchor={0.5} y={4} style={suitStyle} />
          <Text
            text={parsed.rank}
            x={width / 2 - 8}
            y={height / 2 - 8}
            anchor={0.5}
            rotation={Math.PI}
            style={cornerStyle}
          />
        </>
      )}
    </Container>
  );
}

function BoardSlot({ x, y }: { x: number; y: number }) {
  const drawSlot = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x070d18, 0.46);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, CARD_RADIUS);
    graphics.endFill();
    graphics.lineStyle(1, 0x78cfd9, 0.15);
    graphics.drawRoundedRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, CARD_RADIUS);
  }, []);

  return <Graphics x={x} y={y} draw={drawSlot} />;
}

function SeatPanel({
  player,
  x,
  y,
  isHero,
  reducedMotion
}: {
  player: PlayerState;
  x: number;
  y: number;
  isHero: boolean;
  reducedMotion: boolean;
}) {
  const panelRef = useRef<PixiContainer>(null);
  const phase = useRef(0);
  const accent = player.folded ? 0x667185 : player.all_in ? 0xdba45d : isHero ? 0x78cfd9 : 0x82d69a;
  const status = player.folded ? "FOLDED" : player.all_in ? "ALL IN" : player.current_bet > 0 ? `BET ${formatStack(player.current_bet)}` : "READY";

  useTick((delta) => {
    const node = panelRef.current;
    if (!node || reducedMotion) {
      return;
    }
    phase.current += 0.018 * delta;
    node.alpha = player.folded ? 0.5 : 0.9 + Math.sin(phase.current) * 0.04;
  });

  const drawPanel = useCallback(
    (graphics: PixiGraphics) => {
      graphics.clear();
      graphics.beginFill(0x08101c, player.folded ? 0.6 : 0.9);
      graphics.drawRoundedRect(-56, -22, 112, 44, 12);
      graphics.endFill();
      graphics.lineStyle(1, accent, player.folded ? 0.22 : 0.58);
      graphics.drawRoundedRect(-56, -22, 112, 44, 12);

      graphics.beginFill(accent, player.folded ? 0.18 : 0.45);
      graphics.drawCircle(-44, -11, 3);
      graphics.drawCircle(44, -11, 3);
      graphics.endFill();
    },
    [accent, player.folded]
  );

  const nameStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk, Segoe UI, sans-serif",
        fontSize: 12,
        fontWeight: "700",
        fill: player.folded ? 0x8792a6 : 0xf0eadf,
        align: "center"
      }),
    [player.folded]
  );

  const stackStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, sans-serif",
        fontSize: 10,
        fill: player.folded ? 0x667185 : 0x9fd8df,
        align: "center"
      }),
    [player.folded]
  );

  const statusStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, sans-serif",
        fontSize: 8,
        fontWeight: "700",
        fill: accent,
        align: "center",
        dropShadow: !player.folded,
        dropShadowColor: player.all_in ? "#dba45d" : "#78cfd9",
        dropShadowBlur: 2,
        dropShadowDistance: 0
      }),
    [accent, player.all_in, player.folded]
  );

  return (
    <Container ref={panelRef} x={x} y={y}>
      <Graphics draw={drawPanel} />
      <Text text={compactName(player.name || "Player")} anchor={0.5} y={-14} style={nameStyle} />
      <Text text={formatStack(player.bankroll)} anchor={0.5} y={0} style={stackStyle} />
      <Text text={status} anchor={0.5} y={13} style={statusStyle} />
    </Container>
  );
}

function TableScene({
  pot = "$0 POT",
  action = "WAITING...",
  players = [],
  heroCards = [],
  communityCards = []
}: NeonTableProps) {
  const reducedMotion = useReducedMotion();
  const ringRef = useRef<PixiContainer>(null);
  const scannerRef = useRef<PixiContainer>(null);
  const pulseRef = useRef<PixiGraphics>(null);
  const pulse = useRef(0);

  useTick((delta) => {
    if (reducedMotion) {
      return;
    }

    if (ringRef.current) {
      ringRef.current.rotation += 0.001 * delta;
    }
    if (scannerRef.current) {
      scannerRef.current.rotation -= 0.0035 * delta;
    }
    if (pulseRef.current) {
      pulse.current += 0.018 * delta;
      pulseRef.current.alpha = 0.24 + Math.sin(pulse.current) * 0.08;
    }
  });

  const drawTable = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x02050c, 0.98);
    graphics.drawEllipse(0, 0, TABLE_RX + 36, TABLE_RY + 34);
    graphics.endFill();

    graphics.lineStyle(8, 0x06111e, 1);
    graphics.drawEllipse(0, 0, TABLE_RX + 22, TABLE_RY + 22);
    graphics.lineStyle(2, 0x78cfd9, 0.48);
    graphics.drawEllipse(0, 0, TABLE_RX + 15, TABLE_RY + 14);
    graphics.lineStyle(1, 0x82d69a, 0.2);
    graphics.drawEllipse(0, 0, TABLE_RX, TABLE_RY);

    graphics.beginFill(0x07111c, 0.98);
    graphics.drawEllipse(0, 0, TABLE_RX, TABLE_RY);
    graphics.endFill();
    graphics.beginFill(0x050a14, 0.95);
    graphics.drawEllipse(0, 0, INNER_RX, INNER_RY);
    graphics.endFill();

    graphics.lineStyle(1, 0x78cfd9, 0.1);
    for (let radius = 0.32; radius <= 1; radius += 0.22) {
      graphics.drawEllipse(0, 0, INNER_RX * radius, INNER_RY * radius);
    }

    graphics.lineStyle(1, 0x2b5d67, 0.14);
    for (let i = 0; i < 12; i += 1) {
      const point = ellipsePoint((i / 12) * 360, TABLE_RX - 22, TABLE_RY - 18);
      graphics.moveTo(0, 0);
      graphics.lineTo(point.x, point.y);
    }
  }, []);

  const drawGlow = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.lineStyle(7, 0x78cfd9, 0.24);
    graphics.drawEllipse(0, 0, TABLE_RX + 18, TABLE_RY + 17);
    graphics.lineStyle(3, 0x82d69a, 0.1);
    graphics.drawEllipse(0, 0, TABLE_RX - 10, TABLE_RY - 9);
  }, []);

  const drawOrbit = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.lineStyle(1, 0x82d69a, 0.22);
    graphics.drawEllipse(0, 0, TABLE_RX - 42, TABLE_RY - 32);
    graphics.lineStyle(2, 0x78cfd9, 0.26);
    graphics.arc(-TABLE_RX + 88, 0, 24, -0.8, 0.8);
    graphics.arc(TABLE_RX - 88, 0, 24, Math.PI - 0.8, Math.PI + 0.8);
  }, []);

  const drawScanner = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.lineStyle(2, 0x78cfd9, 0.16);
    graphics.moveTo(-INNER_RX + 18, 0);
    graphics.lineTo(INNER_RX - 18, 0);
    graphics.lineStyle(1, 0x82d69a, 0.12);
    graphics.drawEllipse(0, 0, INNER_RX - 30, INNER_RY - 28);
  }, []);

  const drawCenterPlate = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x060d18, 0.9);
    graphics.drawRoundedRect(-86, -34, 172, 68, 14);
    graphics.endFill();
    graphics.lineStyle(1, 0x78cfd9, 0.34);
    graphics.drawRoundedRect(-86, -34, 172, 68, 14);
    graphics.lineStyle(1, 0xf0eadf, 0.08);
    graphics.drawRoundedRect(-73, -23, 146, 46, 10);
  }, []);

  const labelStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, sans-serif",
        fontSize: 10,
        fill: 0x77889c,
        letterSpacing: 2,
        align: "center"
      }),
    []
  );

  const potStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, sans-serif",
        fontSize: 18,
        fontWeight: "700",
        fill: 0x9fd8df,
        align: "center",
        dropShadow: true,
        dropShadowColor: "#78cfd9",
        dropShadowBlur: 4,
        dropShadowDistance: 0
      }),
    []
  );

  const actionStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk, Segoe UI, sans-serif",
        fontSize: 12,
        fontWeight: "600",
        fill: action.toLowerCase().includes("action") ? 0xdba45d : 0xdce8ef,
        align: "center",
        wordWrap: true,
        wordWrapWidth: 146
      }),
    [action]
  );

  const foldedStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Orbitron, Space Grotesk, sans-serif",
        fontSize: 10,
        fill: 0x778296,
        letterSpacing: 1,
        align: "center"
      }),
    []
  );

  const glowFilter = useMemo(() => [new BlurFilter(9)], []);
  const softGlowFilter = useMemo(() => [new BlurFilter(3)], []);

  const seatAngles = [90, -90, -145, -35, 145, 35, 180, 0, 125];
  const activePlayers = players.length > 0 ? players : FALLBACK_PLAYERS;

  const getSeatCoords = (index: number, total: number) => {
    if (total === 2) {
      const angle = index === 0 ? 90 : -90;
      return { ...ellipsePoint(angle, SEAT_RX, SEAT_RY), angle };
    }

    const angle = seatAngles[index % seatAngles.length];
    return { ...ellipsePoint(angle, SEAT_RX, SEAT_RY), angle };
  };

  const getCardPosition = (index: number, total: number) => {
    if (total === 2) {
      return index === 0 ? { x: 0, y: CARD_RY + 12 } : { x: 0, y: -CARD_RY - 4 };
    }

    const coords = getSeatCoords(index, total);
    return ellipsePoint(coords.angle, CARD_RX, CARD_RY);
  };

  const boardX = [-152, -76, 0, 76, 152];
  const boardY = -48;

  return (
    <Container x={CENTER_X} y={CENTER_Y}>
      <Graphics draw={drawTable} />
      <Graphics draw={drawGlow} filters={glowFilter} ref={pulseRef} />
      <Container ref={ringRef}>
        <Graphics draw={drawOrbit} />
      </Container>
      <Container ref={scannerRef}>
        <Graphics draw={drawScanner} filters={softGlowFilter} />
      </Container>

      {boardX.map((slotX) => (
        <BoardSlot key={`slot-${slotX}`} x={slotX} y={boardY} />
      ))}

      {communityCards.map((cardStr, index) => (
        <PlayingCard
          key={`${cardStr}-${index}`}
          card={parseCard(cardStr)}
          x={boardX[index] ?? 0}
          y={boardY}
          delay={index * 0.08}
          reducedMotion={reducedMotion}
        />
      ))}

      <Container y={62}>
        <Graphics draw={drawCenterPlate} />
        <Text text="CYBER FELT" anchor={0.5} y={-23} style={labelStyle} />
        <Text text={pot || "$0"} anchor={0.5} y={-3} style={potStyle} />
        <Text text={action || "Waiting"} anchor={0.5} y={22} style={actionStyle} />
      </Container>

      {activePlayers.map((player, index) => {
        const seat = getSeatCoords(index, activePlayers.length);
        const cardPos = getCardPosition(index, activePlayers.length);
        const isHero = index === 0 || Boolean(player.isHero);
        const showFace = isHero && heroCards.length > 0;
        const firstCard = showFace ? parseCard(heroCards[0]) : undefined;
        const secondCard = showFace && heroCards.length > 1 ? parseCard(heroCards[1]) : undefined;

        return (
          <Container key={`${player.name}-${index}`}>
            <SeatPanel player={player} x={seat.x} y={seat.y} isHero={isHero} reducedMotion={reducedMotion} />

            {player.folded ? (
              <Text text="FOLDED" anchor={0.5} x={cardPos.x} y={cardPos.y} style={foldedStyle} />
            ) : (
              <Container x={cardPos.x} y={cardPos.y}>
                <PlayingCard
                  card={firstCard}
                  x={-18}
                  y={0}
                  rotation={-0.1}
                  faceDown={!showFace}
                  delay={0.05 + index * 0.035}
                  reducedMotion={reducedMotion}
                  compact={!isHero}
                />
                <PlayingCard
                  card={secondCard}
                  x={18}
                  y={2}
                  rotation={0.1}
                  faceDown={!showFace}
                  delay={0.12 + index * 0.035}
                  reducedMotion={reducedMotion}
                  compact={!isHero}
                />
              </Container>
            )}
          </Container>
        );
      })}
    </Container>
  );
}

export default function NeonTable(props: NeonTableProps) {
  const devicePixelRatio = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;

  return (
    <Stage
      width={TABLE_WIDTH}
      height={TABLE_HEIGHT}
      options={{
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: devicePixelRatio
      }}
    >
      <TableScene {...props} />
    </Stage>
  );
}

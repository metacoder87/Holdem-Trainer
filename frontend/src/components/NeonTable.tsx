import { Container, Graphics, Stage, Text, useTick } from "@pixi/react";
import { BlurFilter, TextStyle } from "pixi.js";
import { useCallback, useMemo, useRef } from "react";
import type { Container as PixiContainer, Graphics as PixiGraphics } from "pixi.js";

const TABLE_SIZE = 360;
const CENTER = TABLE_SIZE / 2;
const OUTER_RADIUS = 150;
const INNER_RADIUS = 110;
const CARD_WIDTH = 34;
const CARD_HEIGHT = 48;
const DEAL_DURATION = 32;
const DEAL_DELAY = 8;

const seats = [
  { label: "Coach Bot", angle: -90 },
  { label: "Aggro AI", angle: -30 },
  { label: "Balanced AI", angle: 30 },
  { label: "Hero", angle: 90 },
  { label: "Tight AI", angle: 150 },
  { label: "Wild AI", angle: -150 }
];

const cardTargets = [
  { id: "c1", x: -52, y: -42 },
  { id: "c2", x: -26, y: -42 },
  { id: "c3", x: 0, y: -42 },
  { id: "c4", x: 26, y: -42 },
  { id: "c5", x: 52, y: -42 },
  { id: "h1", x: -22, y: 62 },
  { id: "h2", x: 22, y: 62 }
];

function TableScene() {
  const ringRef = useRef<PixiContainer>(null);
  const pulseRef = useRef<PixiGraphics>(null);
  const cardRefs = useRef<Array<PixiGraphics | null>>([]);
  const pulse = useRef(0);
  const dealProgress = useRef(0);

  useTick((delta) => {
    if (ringRef.current) {
      ringRef.current.rotation += 0.0025 * delta;
    }
    if (pulseRef.current) {
      pulse.current += 0.02 * delta;
      pulseRef.current.alpha = 0.35 + Math.sin(pulse.current) * 0.15;
    }

    dealProgress.current += delta;
    const totalTimeline = DEAL_DURATION + cardTargets.length * DEAL_DELAY + 80;
    if (dealProgress.current > totalTimeline) {
      dealProgress.current = 0;
    }

    cardTargets.forEach((card, index) => {
      const sprite = cardRefs.current[index];
      if (!sprite) return;

      const tRaw = (dealProgress.current - index * DEAL_DELAY) / DEAL_DURATION;
      const t = Math.max(0, Math.min(1, tRaw));
      const eased = 1 - Math.pow(1 - t, 3);
      const bob = t === 1 ? Math.sin((dealProgress.current / 10) + index) * 1.5 : 0;

      sprite.x = card.x * eased;
      sprite.y = 8 + (card.y - 8) * eased + bob;
      sprite.alpha = t;
      sprite.scale.set(0.9 + 0.1 * t);
    });
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

  const drawCard = useCallback((graphics: PixiGraphics) => {
    graphics.clear();
    graphics.beginFill(0x111a27, 0.95);
    graphics.drawRoundedRect(
      -CARD_WIDTH / 2,
      -CARD_HEIGHT / 2,
      CARD_WIDTH,
      CARD_HEIGHT,
      6
    );
    graphics.endFill();
    graphics.lineStyle(1, 0x28f4ff, 0.45);
    graphics.drawRoundedRect(
      -CARD_WIDTH / 2,
      -CARD_HEIGHT / 2,
      CARD_WIDTH,
      CARD_HEIGHT,
      6
    );
    graphics.lineStyle(0);
    graphics.beginFill(0x1bd1b1, 0.6);
    graphics.drawRoundedRect(-10, -14, 20, 6, 3);
    graphics.endFill();
  }, []);

  const seatStyle = useMemo(
    () =>
      new TextStyle({
        fontFamily: "Space Grotesk",
        fontSize: 12,
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

  const glowFilter = useMemo(() => [new BlurFilter(8)], []);

  return (
    <Container x={CENTER} y={CENTER}>
      <Graphics draw={drawTable} />
      <Graphics draw={drawGlow} filters={glowFilter} ref={pulseRef} />
      <Container ref={ringRef}>
        <Graphics draw={drawOrbit} />
      </Container>

      <Text text="LIVE TABLE" anchor={0.5} y={-18} style={centerLabel} />
      <Text text="$12.4K POT" anchor={0.5} y={4} style={centerPot} />
      <Text text="TURN DECISION" anchor={0.5} y={28} style={centerAction} />

      {cardTargets.map((card, index) => (
        <Graphics
          key={card.id}
          draw={drawCard}
          ref={(node) => {
            cardRefs.current[index] = node;
          }}
          alpha={0}
        />
      ))}

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

export default function NeonTable() {
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
      <TableScene />
    </Stage>
  );
}

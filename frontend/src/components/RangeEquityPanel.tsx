import { useEffect, useMemo, useState } from "react";
import RangeGrid from "./RangeGrid";
import {
  getPreflopCharts,
  postRangeEquity,
  type PreflopChartsResponse,
  type RangeClassMap,
  type RangeEquityResult,
} from "../api/client";

/**
 * Range-vs-range equity calculator.
 *
 * Lets the user:
 *   - Pick a preflop chart preset for each player from a dropdown
 *     (UTG_OPEN, BTN_OPEN, BB_DEFEND, TIGHT_3BET, ...) OR type a
 *     notation string ("AA, KK, AKs").
 *   - Optionally enter a board (3-5 cards) to compute postflop
 *     equity.
 *   - See each side's range visualized on a 13x13 grid AND the
 *     per-side equity bars.
 *
 * Hits ``POST /api/poker/range-equity`` for the calculation.
 *
 * No state persistence — pure tool. The user explores a spot and
 * walks away with a number.
 */
type PlayerSlot = {
  kind: "chart" | "range" | "hand";
  chart: string;
  range: string;
  hand: string;
};

function defaultSlot(chart: string): PlayerSlot {
  return { kind: "chart", chart, range: "", hand: "" };
}

function parseHand(hand: string): string[] {
  // Accept "AhKh" / "Ah Kh" / "Ah,Kh".
  const cleaned = hand.replace(/[,\s]+/g, " ").trim();
  if (!cleaned) return [];
  if (cleaned.length === 4 && !cleaned.includes(" ")) {
    // Compact "AhKh" form.
    return [cleaned.slice(0, 2), cleaned.slice(2, 4)];
  }
  return cleaned.split(" ").filter(Boolean);
}

function parseBoard(board: string): string[] {
  return board
    .replace(/[,\s]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean);
}

export default function RangeEquityPanel() {
  const [charts, setCharts] = useState<PreflopChartsResponse | null>(null);
  const [slots, setSlots] = useState<PlayerSlot[]>([
    defaultSlot("TIGHT_3BET"),
    defaultSlot("BTN_OPEN"),
  ]);
  const [board, setBoard] = useState("");
  const [result, setResult] = useState<RangeEquityResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPreflopCharts()
      .then(setCharts)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load charts")
      );
  }, []);

  const chartNames = useMemo(
    () => (charts ? Object.keys(charts.charts) : []),
    [charts]
  );

  const updateSlot = (idx: number, patch: Partial<PlayerSlot>) => {
    setSlots((prev) =>
      prev.map((s, i) => (i === idx ? { ...s, ...patch } : s))
    );
  };

  const addSlot = () => {
    if (slots.length >= 9) return;
    setSlots((prev) => [...prev, defaultSlot("BTN_OPEN")]);
  };

  const removeSlot = (idx: number) => {
    if (slots.length <= 2) return;
    setSlots((prev) => prev.filter((_, i) => i !== idx));
  };

  const compute = async () => {
    setError(null);
    setLoading(true);
    try {
      const players = slots.map((slot) => {
        if (slot.kind === "hand") {
          const cards = parseHand(slot.hand);
          if (cards.length !== 2) {
            throw new Error("Each hand needs exactly 2 cards (e.g. AhKh).");
          }
          return { hand: cards };
        }
        if (slot.kind === "range") {
          if (!slot.range.trim()) {
            throw new Error("Enter a range string or pick a chart.");
          }
          return { range: slot.range.trim() };
        }
        return { preflop_chart: slot.chart };
      });
      const boardCards = parseBoard(board);
      if (boardCards.length && ![3, 4, 5].includes(boardCards.length)) {
        throw new Error("Board must be 0, 3, 4, or 5 cards.");
      }
      const response = await postRangeEquity({
        players,
        board: boardCards.length ? boardCards : undefined,
      });
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Failed to compute equity");
    } finally {
      setLoading(false);
    }
  };

  // For each player slot, fetch its visual range-grid weights from
  // the preflop chart presets when applicable. Hand- and notation-
  // mode slots don't render a grid (no class map available client-
  // side without re-querying the backend).
  const slotWeights = (slot: PlayerSlot): RangeClassMap | null => {
    if (slot.kind === "chart" && charts) {
      return charts.charts[slot.chart] || null;
    }
    return null;
  };

  return (
    <div className="panel range-equity-panel">
      <div className="panel-header">
        <h2>Range vs Range Equity</h2>
        <p>
          Pick a preflop chart or type your own range, set an optional
          board, and run the Monte Carlo. Card removal and multiway
          deals are handled by the solver.
        </p>
      </div>

      <div className="range-equity-slots">
        {slots.map((slot, idx) => (
          <div key={idx} className="range-equity-slot panel">
            <div className="range-equity-slot-header">
              <strong>Player {idx + 1}</strong>
              {slots.length > 2 && (
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => removeSlot(idx)}
                >
                  Remove
                </button>
              )}
            </div>
            <div className="range-equity-slot-controls">
              <label>
                <span className="muted small">Mode</span>
                <select
                  value={slot.kind}
                  onChange={(e) =>
                    updateSlot(idx, {
                      kind: e.target.value as PlayerSlot["kind"],
                    })
                  }
                >
                  <option value="chart">Preflop chart</option>
                  <option value="range">Range string</option>
                  <option value="hand">Specific hand</option>
                </select>
              </label>
              {slot.kind === "chart" && (
                <label>
                  <span className="muted small">Chart</span>
                  <select
                    value={slot.chart}
                    onChange={(e) => updateSlot(idx, { chart: e.target.value })}
                  >
                    {chartNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {slot.kind === "range" && (
                <label>
                  <span className="muted small">Range</span>
                  <input
                    type="text"
                    value={slot.range}
                    onChange={(e) => updateSlot(idx, { range: e.target.value })}
                    placeholder="e.g. 22+, AKs, AKo"
                  />
                </label>
              )}
              {slot.kind === "hand" && (
                <label>
                  <span className="muted small">Hand</span>
                  <input
                    type="text"
                    value={slot.hand}
                    onChange={(e) => updateSlot(idx, { hand: e.target.value })}
                    placeholder="e.g. AhKh"
                  />
                </label>
              )}
            </div>
            {slot.kind === "chart" && slotWeights(slot) && (
              <RangeGrid weights={slotWeights(slot)!} />
            )}
            {result?.players[idx] && (
              <div className="range-equity-meter">
                <div className="range-equity-meter-label">
                  Equity: {(result.players[idx].equity * 100).toFixed(1)}%
                </div>
                <div className="range-equity-meter-bar">
                  <div
                    className="range-equity-meter-fill"
                    style={{
                      width: `${Math.max(2, result.players[idx].equity * 100)}%`,
                    }}
                  />
                </div>
                <div className="muted small">
                  {result.players[idx].combo_count} combo
                  {result.players[idx].combo_count === 1 ? "" : "s"}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="range-equity-controls">
        <button
          type="button"
          className="btn ghost"
          onClick={addSlot}
          disabled={slots.length >= 9}
        >
          + Player
        </button>
        <label>
          <span className="muted small">Board (0/3/4/5 cards)</span>
          <input
            type="text"
            value={board}
            onChange={(e) => setBoard(e.target.value)}
            placeholder="e.g. Qs Jh 2d"
          />
        </label>
        <button
          type="button"
          className="btn primary"
          onClick={compute}
          disabled={loading}
        >
          {loading ? "Computing…" : "Run equity"}
        </button>
      </div>

      {error && <div className="warn">{error}</div>}
    </div>
  );
}

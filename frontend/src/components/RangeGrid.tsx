import { useMemo } from "react";
import type { RangeClassMap } from "../api/client";

/**
 * 13x13 poker hand matrix.
 *
 * Rendering convention (standard across PioSolver / Flopzilla / etc):
 *   - Rows = high card rank (A, K, Q, ..., 2).
 *   - Cols = low card rank (A, K, ..., 2).
 *   - Diagonal (row == col)  -> pocket pair (e.g. AA, KK).
 *   - Above diagonal (row<col) -> suited (e.g. AKs).
 *   - Below diagonal (row>col) -> offsuit (e.g. AKo).
 *
 * Each cell renders the class label with a colored background whose
 * intensity reflects the weight in [0, 1]. Click toggles inclusion if
 * an ``onToggle`` callback is provided (range-editor mode); read-only
 * mode shows the cell without click handlers.
 */
type Props = {
  /** Class-string -> weight in [0, 1]. Missing keys render as empty. */
  weights: RangeClassMap;
  /** Optional toggle callback: receives the class string clicked. */
  onToggle?: (classString: string) => void;
  /** Optional small label rendered above the grid. */
  title?: string;
  /** Optional secondary weights for overlay (e.g. opponent vs hero). */
  overlayWeights?: RangeClassMap;
};

const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"];

function classLabel(rowIdx: number, colIdx: number): string {
  const hi = RANKS[rowIdx];
  const lo = RANKS[colIdx];
  if (rowIdx === colIdx) return `${hi}${lo}`;
  // Convention: row < col -> suited (upper triangle), else offsuit.
  if (rowIdx < colIdx) return `${hi}${lo}s`;
  // For below-diagonal cells the "high" rank is actually the column.
  return `${lo}${hi}o`;
}

function bgFromWeight(weight: number, off = false): string {
  if (!weight || weight <= 0) {
    return "rgba(60, 80, 100, 0.18)";
  }
  // Suited cells use cyan-ish, offsuit cells use green-ish so the
  // upper/lower triangles are visually distinguishable even without
  // labels.
  const alpha = 0.18 + Math.min(1.0, weight) * 0.72;
  if (off) {
    return `rgba(130, 214, 154, ${alpha})`;
  }
  return `rgba(120, 207, 217, ${alpha})`;
}

export default function RangeGrid({
  weights,
  onToggle,
  title,
  overlayWeights,
}: Props) {
  // Pre-build the 13x13 cells in one pass.
  const cells = useMemo(() => {
    const out: Array<{
      row: number;
      col: number;
      label: string;
      weight: number;
      overlay: number;
      isPair: boolean;
      isSuited: boolean;
    }> = [];
    for (let r = 0; r < 13; r++) {
      for (let c = 0; c < 13; c++) {
        // For below-diagonal offsuit cells, the canonical class
        // string uses the COLUMN as the high rank, which means we
        // index the weights map by the offsuit class key. But the
        // class label still reads from grid coords (lookup key is
        // the same string).
        const label = classLabel(r, c);
        const weight = weights[label] || 0;
        const overlay = overlayWeights?.[label] || 0;
        out.push({
          row: r,
          col: c,
          label,
          weight,
          overlay,
          isPair: r === c,
          isSuited: r < c,
        });
      }
    }
    return out;
  }, [weights, overlayWeights]);

  return (
    <div className="range-grid">
      {title && <div className="range-grid-title">{title}</div>}
      <div className="range-grid-table">
        {cells.map((cell) => {
          const isClickable = Boolean(onToggle);
          const bg = bgFromWeight(cell.weight, !cell.isSuited && !cell.isPair);
          const overlayBg = cell.overlay
            ? bgFromWeight(cell.overlay, !cell.isSuited && !cell.isPair)
            : null;
          return (
            <button
              key={cell.label}
              type="button"
              className={`range-grid-cell ${
                cell.isPair ? "pair" : cell.isSuited ? "suited" : "offsuit"
              }`}
              style={{ background: bg }}
              onClick={() => onToggle?.(cell.label)}
              disabled={!isClickable}
              title={`${cell.label} · weight ${cell.weight.toFixed(2)}${
                cell.overlay ? ` · overlay ${cell.overlay.toFixed(2)}` : ""
              }`}
              aria-label={`${cell.label} weight ${cell.weight.toFixed(2)}`}
            >
              {overlayBg && (
                <span
                  className="range-grid-overlay"
                  style={{ background: overlayBg }}
                />
              )}
              <span className="range-grid-label">{cell.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

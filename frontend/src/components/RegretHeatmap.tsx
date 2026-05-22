import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getRegretHeatmap,
  type RegretHeatmapReport,
  type RegretHeatmapCell,
} from "../api/client";

/**
 * Regret heatmap panel.
 *
 * Shows where in the strategy space (street x position x SPR bucket)
 * a player concentrates their EV loss. Dominant cells are the
 * structural leaks. Clicking a cell pulls one of its example
 * decisions and seeds a drill for the exact spot.
 *
 * Why a heatmap, not another table: existing EV-leak views group by
 * (action, recommended action). That tells you what action you keep
 * getting wrong. The heatmap tells you *where* in the game you keep
 * making mistakes — a more useful signal for structured study.
 */
type Props = {
  player: string | undefined;
};

const STREETS = ["preflop", "flop", "turn", "river"] as const;
type Street = (typeof STREETS)[number];

const SPR_LABELS: Record<number, string> = {
  0: "?",
  1: "≤3",
  2: "3-6",
  3: "6-12",
  4: "12-25",
  5: ">25",
};

function tone(loss: number, max: number): string {
  if (max <= 0) return "0";
  const t = Math.max(0, Math.min(1, loss / max));
  return t.toFixed(2);
}

export default function RegretHeatmap({ player }: Props) {
  const [report, setReport] = useState<RegretHeatmapReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!player) {
      setReport(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRegretHeatmap(player)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load heatmap");
        setReport(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [player]);

  // Build a (street, spr_bucket) -> aggregated cell map. The backend
  // returns position-keyed cells too, but for the headline grid we
  // pool positions together for visual density.
  const grid = new Map<string, { ev: number; count: number; cells: RegretHeatmapCell[] }>();
  let gridMax = 0;
  for (const cell of report?.cells ?? []) {
    const key = `${cell.street}|${cell.spr_bucket}`;
    const entry = grid.get(key) || { ev: 0, count: 0, cells: [] };
    entry.ev += cell.total_ev_loss_bb;
    entry.count += cell.decision_count;
    entry.cells.push(cell);
    grid.set(key, entry);
    if (entry.ev > gridMax) gridMax = entry.ev;
  }

  const sprBuckets = [1, 2, 3, 4, 5];

  function practiceCell(cell: RegretHeatmapCell) {
    if (!player) return;
    const example = cell.example_keys?.[0];
    if (!example || example.hand_number === null) {
      setSeedError("This cell has no recorded examples to practice.");
      return;
    }
    // Navigate to the Drill page with the (hand, decision) coordinates;
    // Drill.tsx handles the actual POST to /training/drill/from-decision.
    navigate(
      `/training/drill?from_decision_hand=${example.hand_number}` +
        `&from_decision_idx=${example.decision_index}`
    );
  }

  return (
    <div className="panel regret-heatmap-panel">
      <div className="panel-header">
        <h2>Regret heatmap</h2>
        <p>
          EV-loss density by street × stack-to-pot ratio. Darker cells =
          more chips lost in that structural spot. Click any cell to
          practice an example decision from your history.
        </p>
      </div>

      {loading && <div className="muted">Loading heatmap…</div>}
      {error && <div className="warn">{error}</div>}

      {report && (
        <>
          <div className="heatmap-totals">
            <div className="stat-card">
              <div className="stat-label">Tracked decisions</div>
              <div className="stat-value">{report.totals.decisions}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total EV lost</div>
              <div className={`stat-value ${report.totals.ev_loss_bb > 0 ? "warn" : ""}`}>
                {report.totals.ev_loss_bb.toFixed(2)} BB
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Worst cell</div>
              <div className="stat-value">{report.max_loss_bb.toFixed(2)} BB</div>
            </div>
          </div>

          <div className="heatmap-grid-wrap">
            <table className="heatmap-grid">
              <thead>
                <tr>
                  <th />
                  {sprBuckets.map((b) => (
                    <th key={b}>SPR {SPR_LABELS[b]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {STREETS.map((street: Street) => (
                  <tr key={street}>
                    <th>{street}</th>
                    {sprBuckets.map((b) => {
                      const key = `${street}|${b}`;
                      const entry = grid.get(key);
                      if (!entry || entry.count === 0) {
                        return (
                          <td key={b} className="heatmap-cell empty" title="No decisions">
                            <span className="muted small">—</span>
                          </td>
                        );
                      }
                      const intensity = tone(entry.ev, gridMax);
                      // Pick the worst (largest EV-loss) underlying cell
                      // as the click target so practicing it gives you
                      // the most relevant example.
                      const worst = entry.cells.slice().sort(
                        (a, b) => b.total_ev_loss_bb - a.total_ev_loss_bb
                      )[0];
                      return (
                        <td
                          key={b}
                          className="heatmap-cell"
                          style={{
                            background: `rgba(255, 90, 90, ${Number(intensity) * 0.55})`,
                            cursor: worst.example_keys?.length ? "pointer" : "default",
                          }}
                          title={`${entry.count} decisions, ${entry.ev.toFixed(2)} BB lost — click to practice`}
                          onClick={() => worst && practiceCell(worst)}
                        >
                          <div className="cell-value">{entry.ev.toFixed(1)} BB</div>
                          <div className="cell-meta">{entry.count} dec</div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {seedError && <div className="warn">{seedError}</div>}

          {report.cells.length === 0 && (
            <div className="muted">
              No priced decisions yet. Play tracked hands with training
              feedback enabled to populate the heatmap.
            </div>
          )}
        </>
      )}
    </div>
  );
}

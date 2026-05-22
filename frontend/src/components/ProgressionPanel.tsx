import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getAdaptiveProgression,
  postSrsReview,
  type AdaptiveProgressionReport,
  type BanditArmReport,
} from "../api/client";

/**
 * Track-4 adaptive progression dashboard.
 *
 * Surfaces three quant-flavored learning subsystems:
 *
 *  - **Bandit arms** (Thompson sampling): per-topic Beta posterior +
 *    95% CI. The "next topic" chip shows which arm the bandit would
 *    pull right now.
 *  - **SRS deck** (SM-2): how many cards are due for review, total
 *    deck size, and a compact list of due card IDs.
 *  - **Elo rating**: player rating + attempt count + number of
 *    scenarios tracked.
 *
 * The user can also fire an SM-2 review directly from the panel by
 * clicking a quality button on a due card — the response updates the
 * full panel state in-place, so the user sees the next due card
 * recompute immediately.
 */
type Props = {
  player: string | undefined;
};

const QUALITIES = [
  { value: 5, label: "Easy" },
  { value: 4, label: "Good" },
  { value: 3, label: "Hard" },
  { value: 1, label: "Missed" },
] as const;

function formatTopic(topic: string): string {
  return topic.replace(/_/g, " ");
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function ArmRow({ arm, highlight }: { arm: BanditArmReport; highlight: boolean }) {
  // Bar showing expected accuracy + filled CI band.
  const width = `${Math.max(0, Math.min(100, arm.expected_accuracy * 100))}%`;
  const lo = `${Math.max(0, Math.min(100, arm.ci_lower * 100))}%`;
  const hi = `${Math.max(0, Math.min(100, arm.ci_upper * 100))}%`;
  return (
    <div className={`progression-arm-row ${highlight ? "highlight" : ""}`}>
      <div className="progression-arm-header">
        <span className="progression-arm-topic">{formatTopic(arm.topic)}</span>
        <span className="progression-arm-mean">{pct(arm.expected_accuracy)}</span>
      </div>
      <div className="progression-arm-bar">
        <span
          className="progression-arm-ci"
          style={{
            left: lo,
            right: `calc(100% - ${hi})`,
          }}
        />
        <span className="progression-arm-mean-bar" style={{ width }} />
      </div>
      <div className="progression-arm-meta muted small">
        CI {pct(arm.ci_lower)} – {pct(arm.ci_upper)} · {arm.pulls} attempt{arm.pulls === 1 ? "" : "s"}
      </div>
    </div>
  );
}

export default function ProgressionPanel({ player }: Props) {
  const [report, setReport] = useState<AdaptiveProgressionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);

  const refresh = () => {
    if (!player) {
      setReport(null);
      return;
    }
    setLoading(true);
    setError(null);
    getAdaptiveProgression(player)
      .then(setReport)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load progression")
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player]);

  const submitReview = async (cardId: string, quality: number) => {
    if (!player) return;
    setReviewing(cardId);
    try {
      const updated = await postSrsReview({
        player,
        card_id: cardId,
        quality,
      });
      setReport(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setReviewing(null);
    }
  };

  return (
    <div className="panel progression-panel">
      <div className="panel-header">
        <h2>Adaptive progression</h2>
        <p>
          Thompson-sampling bandit on weakness topics, SM-2 spaced
          repetition for memorized atoms, Elo for scenario difficulty.
          The next drill topic is the bandit's lowest-confidence arm.
        </p>
      </div>

      {loading && <div className="muted">Loading…</div>}
      {error && <div className="warn">{error}</div>}

      {report && (
        <>
          <div className="progression-summary-cards">
            <div className="stat-card">
              <div className="stat-label">Next topic</div>
              <div className="stat-value">
                {report.next_topic ? formatTopic(report.next_topic) : "—"}
              </div>
              <div className="stat-delta muted">picked by Thompson sampling</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">SRS due</div>
              <div className={`stat-value ${report.srs.due_count > 0 ? "warn" : ""}`}>
                {report.srs.due_count}
              </div>
              <div className="stat-delta muted">
                {report.srs.total_cards} card{report.srs.total_cards === 1 ? "" : "s"} tracked
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Elo rating</div>
              <div className="stat-value">{report.elo.player_rating.toFixed(0)}</div>
              <div className="stat-delta muted">
                {report.elo.attempts} attempt{report.elo.attempts === 1 ? "" : "s"} · {report.elo.tracked_scenarios} scenario{report.elo.tracked_scenarios === 1 ? "" : "s"}
              </div>
            </div>
          </div>

          <div className="progression-section">
            <h3>Topic mastery (Bayesian posterior)</h3>
            <div className="progression-arms">
              {report.bandit.map((arm) => (
                <ArmRow
                  key={arm.topic}
                  arm={arm}
                  highlight={arm.topic === report.next_topic}
                />
              ))}
            </div>
          </div>

          {report.srs.due_card_ids.length > 0 && (
            <div className="progression-section">
              <h3>Due for SRS review</h3>
              <p className="muted small">
                Rate your recall on each card. 5 = perfect, 1 = missed.
                SM-2 schedules the next review based on the rating.
              </p>
              <ul className="srs-due-list">
                {report.srs.due_card_ids.map((cardId) => (
                  <li key={cardId} className="srs-due-row">
                    <span className="srs-card-id">{cardId}</span>
                    <div className="srs-quality-buttons">
                      {QUALITIES.map((q) => (
                        <button
                          key={q.value}
                          type="button"
                          className={`btn ghost srs-quality-${q.value}`}
                          disabled={reviewing === cardId}
                          onClick={() => submitReview(cardId, q.value)}
                        >
                          {q.label}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="progression-actions">
            <Link className="btn primary" to="/training/drill">
              Run next drill
            </Link>
            <Link className="btn ghost" to="/learn">
              Browse learn material
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

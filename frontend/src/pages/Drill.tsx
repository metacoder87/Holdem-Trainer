import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  evaluateTrainingDrill,
  getTrainingDrill,
  getTrainingProgress,
  postDrillFromDecision,
  type DrillEvaluation,
  type FocusQueueItem,
  type TrainingDrill,
  type TrainingProgress
} from "../api/client";

export default function Drill() {
  const { summary, activePlayer, refreshSummary } = useOutletContext<ShellContext>();
  const [searchParams] = useSearchParams();
  const requestedFocus = searchParams.get("focus") || undefined;
  // Track 3: drill seeded from a specific historical decision.
  const fromDecisionHand = searchParams.get("from_decision_hand");
  const fromDecisionIdx = searchParams.get("from_decision_idx");
  const player = activePlayer || summary.player.name || "Guest";
  const [drill, setDrill] = useState<TrainingDrill | null>(null);
  const [progress, setProgress] = useState<TrainingProgress | null>(null);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<DrillEvaluation | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const loadDrill = useCallback(() => {
    // When the route carries (from_decision_hand, from_decision_idx)
    // we seed the drill from that exact historical decision rather
    // than asking the trainer for a generic weakness-focused one.
    if (fromDecisionHand && fromDecisionIdx) {
      const handNumber = Number(fromDecisionHand);
      const decisionIndex = Number(fromDecisionIdx);
      if (
        Number.isFinite(handNumber) &&
        Number.isFinite(decisionIndex) &&
        player
      ) {
        postDrillFromDecision({
          player,
          hand_number: handNumber,
          decision_index: decisionIndex,
        })
          .then((response) => {
            if (response.drill) {
              // Backend returns a richer payload than TrainingDrill;
              // cast through unknown so TS accepts the shape overlap.
              setDrill(response.drill as unknown as TrainingDrill);
              setAnswer("");
              setEvaluation(null);
              setStatus(null);
            } else {
              setStatus(
                response.error || "Could not seed a drill from that decision."
              );
            }
          })
          .catch((err) => {
            setStatus(err instanceof Error ? err.message : "Failed to seed drill.");
          });
        return;
      }
    }
    getTrainingDrill(player, requestedFocus)
      .then((data) => {
        setDrill(data);
        setAnswer("");
        setEvaluation(null);
        setStatus(null);
      })
      .catch((err) => {
        setStatus(err instanceof Error ? err.message : "Failed to load drill.");
      });
  }, [player, requestedFocus, fromDecisionHand, fromDecisionIdx]);

  const refreshProgress = useCallback(() => {
    getTrainingProgress(player)
      .then(setProgress)
      .catch(() => null);
  }, [player]);

  useEffect(() => {
    loadDrill();
    refreshProgress();
  }, [loadDrill, refreshProgress]);

  const handleSubmit = async () => {
    if (!drill || !answer.trim()) {
      setStatus("Enter an answer for this drill.");
      return;
    }
    try {
      const result = await evaluateTrainingDrill(drill.drill_id, answer.trim(), player);
      setEvaluation(result);
      setStatus(null);
      refreshProgress();
      refreshSummary?.();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to submit drill.");
    }
  };

  const scenario = drill?.scenario ?? {};
  const mastery = drill ? progress?.mastery_progress?.[drill.focus_area] : undefined;
  const focusCards: FocusQueueItem[] = summary.focus_queue_items?.length
    ? summary.focus_queue_items
    : (summary.focus_queue.length ? summary.focus_queue : progress?.study_recommendations ?? [])
        .slice(0, 4)
        .map((label) => ({ label }));

  return (
    <>
      <section className="section">
        <div className="section-header">
          <div>
            <h2>Guided Drill</h2>
            <p>{drill ? `Current focus: ${drill.focus_area.replace(/_/g, " ")}` : "Loading a tracked practice spot."}</p>
          </div>
          <button className="btn ghost" type="button" onClick={loadDrill}>
            New Drill
          </button>
        </div>
        {status && <div className="form-status">{status}</div>}
        <div className="card-grid">
          {focusCards.map((item) => (
            <div key={`${item.id ?? "label"}-${item.label}`} className="panel module-card">
              <div className="module-label">Focus</div>
              <h3>{item.label}</h3>
              <p>Practice results update this profile's training progress.</p>
              {item.id && (
                <Link className="inline-focus-link" to={`/training/drill?focus=${encodeURIComponent(item.id)}`}>
                  Practice this focus
                </Link>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Scenario</h2>
            <p>{String(scenario.situation ?? "Load a drill to see the current training spot.")}</p>
          </div>
          <ul className="focus-list">
            <li>Position: {String(scenario.your_position ?? "dynamic")}</li>
            <li>Pot: ${String(scenario.pot_size ?? 0)}</li>
            <li>Opponents: {String(scenario.opponents ?? "varies")}</li>
            {drill?.quiz?.question && <li>{String(drill.quiz.question)}</li>}
          </ul>
          <label className="drill-answer">
            Your line
            <input
              type="text"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="Example: call, fold, bet, raise, pause"
            />
          </label>
          <div className="hero-actions">
            <button className="btn primary" type="button" onClick={handleSubmit}>
              Submit Drill
            </button>
            <Link className="btn ghost" to="/training">
              Back to Training
            </Link>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Review</h2>
            <p>{mastery == null ? "Mastery updates after completed drills." : `Current mastery: ${mastery}%`}</p>
          </div>
          {evaluation ? (
            <>
              <div className={`quiz-result ${evaluation.correct ? "good" : "warn"}`}>
                {evaluation.feedback}
              </div>
              <ul className="focus-list">
                {evaluation.recommended_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
                {evaluation.explanation && <li>{evaluation.explanation}</li>}
              </ul>
            </>
          ) : (
            <ul className="focus-list">
              <li>Submit an answer to reveal the recommended line.</li>
              <li>Each attempt is saved to training progress.</li>
            </ul>
          )}
        </div>
      </section>
    </>
  );
}

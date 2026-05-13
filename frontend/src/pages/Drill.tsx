import { useEffect, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  createDrill,
  gradeDrill,
  getDrillFocusAreas,
  type Drill,
  type DrillGrade,
  type FocusArea
} from "../api/client";

export default function Drill() {
  const { activePlayer, summary } = useOutletContext<ShellContext>();
  const [searchParams] = useSearchParams();
  const initialFocus = searchParams.get("focus") ?? "";

  const [focusAreas, setFocusAreas] = useState<FocusArea[]>([]);
  const [focus, setFocus] = useState<string>(initialFocus);
  const [difficulty, setDifficulty] = useState<number>(2);
  const [drill, setDrill] = useState<Drill | null>(null);
  const [grade, setGrade] = useState<DrillGrade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<{ correct: boolean; focus: string }[]>([]);

  useEffect(() => {
    getDrillFocusAreas()
      .then((data) => setFocusAreas(data))
      .catch((err) => setError(err.message || "Failed to load focus areas"));
  }, []);

  const startDrill = async () => {
    setError(null);
    setGrade(null);
    setLoading(true);
    try {
      const next = await createDrill({
        player_name: activePlayer || undefined,
        focus_area: focus || undefined,
        difficulty
      });
      setDrill(next);
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (option: string) => {
    if (!drill) return;
    try {
      const result = await gradeDrill({
        drill_id: drill.drill_id,
        kind: drill.kind,
        correct_action: drill.correct_action,
        user_answer: option,
        player_name: activePlayer || undefined,
        focus_area: drill.focus_area
      });
      setGrade(result);
      setHistory((prev) => [
        { correct: result.correct, focus: drill.focus_area },
        ...prev.slice(0, 9)
      ]);
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    }
  };

  const accuracy = history.length === 0
    ? 0
    : Math.round((history.filter((h) => h.correct).length / history.length) * 100);

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Guided Drill</h2>
          <p>
            Scenario-based reps tailored to{" "}
            {activePlayer ? `${activePlayer}'s` : "your"} highest-priority leaks.
          </p>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Drill Setup</h2>
            <p>Pick a focus area and difficulty, or let the engine choose based on your latest session.</p>
          </div>
          <div className="bankroll-form">
            <label>
              Focus area
              <select value={focus} onChange={(event) => setFocus(event.target.value)}>
                <option value="">Auto (from your weaknesses)</option>
                {focusAreas.map((area) => (
                  <option key={area.id} value={area.id}>
                    {area.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Difficulty
              <select
                value={difficulty}
                onChange={(event) => setDifficulty(Number(event.target.value))}
              >
                <option value={1}>1 - Light</option>
                <option value={2}>2 - Standard</option>
                <option value={3}>3 - Pressure</option>
                <option value={4}>4 - Crucible</option>
              </select>
            </label>
            <button className="btn primary" type="button" onClick={startDrill} disabled={loading}>
              {drill ? "New Scenario" : "Start Drill"}
            </button>
            {error && <div className="form-status">{error}</div>}
          </div>
        </div>
      </section>

      {drill && (
        <section className="section split">
          <div className="panel">
            <div className="panel-header">
              <h2>Scenario</h2>
              <p>Focus: {drill.focus_area.replace(/_/g, " ")}</p>
            </div>
            <div className="quiz-card">
              <pre className="quiz-question">{drill.scenario}</pre>
              <div className="action-grid">
                {drill.options.map((option) => (
                  <button
                    key={option}
                    className={`btn ${grade ? "ghost" : "primary"}`}
                    type="button"
                    onClick={() => submitAnswer(option)}
                    disabled={grade !== null}
                  >
                    {option}
                  </button>
                ))}
              </div>
              {grade && (
                <div className={`quiz-result ${grade.correct ? "good" : "warn"}`}>
                  {grade.feedback}
                </div>
              )}
              <details className="quiz-explain">
                <summary>Context</summary>
                <pre>{JSON.stringify(drill.context, null, 2)}</pre>
              </details>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2>Performance</h2>
              <p>{history.length} drill{history.length === 1 ? "" : "s"} this session</p>
            </div>
            <div className="hero-stats">
              <div className="stat-card">
                <div className="stat-label">Accuracy</div>
                <div className={`stat-value ${accuracy >= 60 ? "good" : "warn"}`}>{accuracy}%</div>
              </div>
            </div>
            <div className="timeline">
              {history.length === 0 && (
                <div className="timeline-item">
                  <div className="timeline-body">
                    <div className="timeline-label">No attempts yet</div>
                    <div className="timeline-detail">Submit an answer to start tracking.</div>
                  </div>
                </div>
              )}
              {history.map((entry, index) => (
                <div key={index} className="timeline-item">
                  <div className="timeline-time">#{history.length - index}</div>
                  <div className="timeline-body">
                    <div className={`timeline-label ${entry.correct ? "good" : "warn"}`}>
                      {entry.correct ? "Correct" : "Missed"}
                    </div>
                    <div className="timeline-detail">{entry.focus.replace(/_/g, " ")}</div>
                  </div>
                </div>
              ))}
            </div>
            <Link className="btn ghost" to="/training">
              Back to Training
            </Link>
          </div>
        </section>
      )}

      {!drill && (
        <section className="section">
          <div className="panel">
            <div className="panel-header">
              <h2>Focus Queue</h2>
              <p>Suggested drills derived from your latest session.</p>
            </div>
            <ul className="focus-list">
              {(summary.focus_queue || []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </>
  );
}

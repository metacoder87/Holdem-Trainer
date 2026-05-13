import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  evaluateTrainingQuiz,
  getTrainingContent,
  getTrainingQuiz,
  type TrainingContent,
  type TrainingQuiz,
  type QuizEvaluation
} from "../api/client";

export default function Training() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [content, setContent] = useState<TrainingContent | null>(null);
  const [quizType, setQuizType] = useState("pot_odds");
  const [quiz, setQuiz] = useState<TrainingQuiz | null>(null);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<QuizEvaluation | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getTrainingContent()
      .then((data) => setContent(data))
      .catch((err) => setStatus(err.message || "Failed to load training content"));
  }, []);

  const tips = useMemo(() => content?.tips?.slice(0, 4) ?? [], [content]);

  const handleQuiz = async () => {
    try {
      const newQuiz = await getTrainingQuiz(quizType);
      setQuiz(newQuiz);
      setEvaluation(null);
      setAnswer("");
      setStatus(null);
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    }
  };

  const handleEvaluate = async () => {
    if (!quiz) return;
    const value = Number(answer);
    if (Number.isNaN(value)) {
      setStatus("Enter a numeric answer.");
      return;
    }
    try {
      const result = await evaluateTrainingQuiz(quiz.correct_answer, value, 0.05, {
        playerName: activePlayer ?? undefined,
        quizType: quiz.type ?? quizType
      });
      setEvaluation(result);
      setStatus(null);
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    }
  };

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Training Command Center</h2>
          <p>Launch drills, track weaknesses, and keep the learning loop tight.</p>
        </div>
        <div className="card-grid">
          {summary.training_tracks.map((track) => (
            <div key={track.title} className="panel module-card">
              <div className="module-label">{track.cadence}</div>
              <h3>{track.title}</h3>
              <p>{track.summary}</p>
              <div className="module-footer">
                <span className="module-intensity">{track.intensity}</span>
                <div className="progress">
                  <span style={{ width: `${track.progress}%` }} />
                </div>
                <span className="progress-text">{track.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section split">
        <div className="panel focus-panel">
          <div className="panel-header">
            <h2>Focus Queue</h2>
            <p>Priority drills derived from your last session data.</p>
          </div>
          <ul className="focus-list">
            {(summary.focus_queue_items ?? summary.focus_queue.map((label) => ({ id: null, label }))).map((item) => (
              <li key={item.label}>
                {item.id ? (
                  <Link to={`/training/drill?focus=${encodeURIComponent(item.id)}`}>
                    {item.label}
                  </Link>
                ) : (
                  item.label
                )}
              </li>
            ))}
          </ul>
          <Link className="btn primary" to="/training/drill">
            Start Guided Drill
          </Link>
        </div>

        <div className="panel timeline-panel">
          <div className="panel-header">
            <h2>Poker Math Quiz</h2>
            <p>Run a quick quiz and get instant feedback.</p>
          </div>
          <div className="quiz-panel">
            <label>
              Quiz type
              <select value={quizType} onChange={(event) => setQuizType(event.target.value)}>
                <option value="pot_odds">Pot Odds</option>
                <option value="required_equity">Required Equity</option>
                <option value="implied_odds">Implied Odds</option>
                <option value="bet_sizing">Bet Sizing</option>
              </select>
            </label>
            <div className="hero-actions">
              <button className="btn primary" type="button" onClick={handleQuiz}>
                Generate Quiz
              </button>
              <Link className="btn ghost" to="/replay">
                Jump to Replay
              </Link>
            </div>
            {quiz && (
              <div className="quiz-card">
                <pre className="quiz-question">{quiz.question}</pre>
                <label>
                  Your answer
                  <input
                    type="number"
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    placeholder="Enter your answer"
                  />
                </label>
                <div className="hero-actions">
                  <button className="btn primary" type="button" onClick={handleEvaluate}>
                    Check Answer
                  </button>
                  <button className="btn ghost" type="button" onClick={handleQuiz}>
                    New Quiz
                  </button>
                </div>
                {evaluation && (
                  <div className={`quiz-result ${evaluation.correct ? "good" : "warn"}`}>
                    {evaluation.feedback}
                  </div>
                )}
                <details className="quiz-explain">
                  <summary>Explanation</summary>
                  <pre>{quiz.explanation}</pre>
                </details>
              </div>
            )}
            {status && <div className="form-status">{status}</div>}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-header">
          <h2>Coach Library</h2>
          <p>Short, high-impact tips pulled from the training content bank.</p>
        </div>
        <div className="card-grid">
          {tips.map((tip) => (
            <div key={tip.title} className="panel module-card">
              <div className="module-label">{tip.category ?? "Tip"}</div>
              <h3>{tip.title}</h3>
              <p>{tip.content}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

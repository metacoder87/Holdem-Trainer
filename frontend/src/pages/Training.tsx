import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import {
  evaluateTrainingQuiz,
  getPlayers,
  getTrainingContent,
  getTrainingProgress,
  getTrainingQuiz,
  type PlayerSummary,
  type QuizEvaluation,
  type TrainingContent,
  type TrainingProgress,
  type TrainingQuiz
} from "../api/client";

export default function Training() {
  const { summary, activePlayer, setActivePlayer } = useOutletContext<ShellContext>();
  const player = activePlayer || summary.player.name || "Guest";
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [content, setContent] = useState<TrainingContent | null>(null);
  const [progress, setProgress] = useState<TrainingProgress | null>(null);
  const [quizType, setQuizType] = useState("pot_odds");
  const [quiz, setQuiz] = useState<TrainingQuiz | null>(null);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<QuizEvaluation | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const refreshProgress = useCallback(() => {
    getTrainingProgress(player)
      .then((data) => setProgress(data))
      .catch(() => null);
  }, [player]);

  useEffect(() => {
    getTrainingContent()
      .then((data) => setContent(data))
      .catch((err) => setStatus(err.message || "Failed to load training content"));
    getPlayers()
      .then(setPlayers)
      .catch(() => setPlayers([]));
  }, []);

  useEffect(() => {
    refreshProgress();
  }, [refreshProgress]);

  const tips = useMemo(() => content?.tips?.slice(0, 4) ?? [], [content]);
  const focusItems = summary.focus_queue.length
    ? summary.focus_queue
    : progress?.study_recommendations?.slice(0, 4) ?? [];

  const handleQuiz = async () => {
    try {
      const newQuiz = await getTrainingQuiz(quizType, player);
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
      const result = await evaluateTrainingQuiz(quiz.quiz_id, value, player, 0.05);
      setEvaluation(result);
      setStatus(null);
      refreshProgress();
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
          <div>
            <h2>Training Command Center</h2>
            <p>Player-owned quizzes, drills, and study priorities.</p>
          </div>
          <label className="inline-select">
            Profile
            <select value={player} onChange={(event) => setActivePlayer?.(event.target.value)}>
              <option value={player}>{player}</option>
              {players
                .filter((item) => item.name !== player)
                .map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
            </select>
          </label>
        </div>
        {summary.training_tracks.length > 0 ? (
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
        ) : (
          <div className="panel module-card">
            <div className="module-label">No tracked sessions</div>
            <h3>Training tracks appear after recorded play</h3>
            <p>Start a session with training enabled to populate progress and focus areas.</p>
          </div>
        )}
      </section>

      <section className="section split">
        <div className="panel focus-panel">
          <div className="panel-header">
            <h2>Focus Queue</h2>
            <p>Priorities derived from tracked weaknesses and drill results.</p>
          </div>
          <ul className="focus-list">
            {focusItems.length > 0 ? (
              focusItems.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li>No focus items yet. Complete a quiz or drill to start a plan.</li>
            )}
          </ul>
          <Link className="btn primary" to="/training/drill">
            Start Guided Drill
          </Link>
        </div>

        <div className="panel timeline-panel">
          <div className="panel-header">
            <h2>Poker Math Quiz</h2>
            <p>Answers are graded by the server and saved to this profile.</p>
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
                    {evaluation.explanation && <pre>{evaluation.explanation}</pre>}
                  </div>
                )}
              </div>
            )}
            {progress && (
              <div className="demo-row">
                <span>Quiz accuracy</span>
                <span>
                  {progress.quiz_stats.accuracy == null
                    ? "-"
                    : `${Math.round(progress.quiz_stats.accuracy * 100)}%`}
                </span>
              </div>
            )}
            {status && <div className="form-status">{status}</div>}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-header">
          <h2>Coach Library</h2>
          <p>Short reference notes from the training content bank.</p>
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

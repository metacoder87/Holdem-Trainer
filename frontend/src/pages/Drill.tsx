import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";
import { getTrainingDrill, type TrainingDrill } from "../api/client";

export default function Drill() {
  const { summary, activePlayer } = useOutletContext<ShellContext>();
  const [drill, setDrill] = useState<TrainingDrill | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getTrainingDrill(activePlayer || summary.player.name)
      .then((data) => {
        setDrill(data);
        setStatus(null);
      })
      .catch((err) => {
        setStatus(err instanceof Error ? err.message : "Failed to load drill.");
      });
  }, [activePlayer, summary.player.name]);

  const scenario = drill?.scenario ?? {};

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Guided Drill</h2>
          <p>{drill ? `Current focus: ${drill.focus_area.replace(/_/g, " ")}` : "Scenario-based reps tailored to your highest-priority leaks."}</p>
        </div>
        {status && <div className="form-status">{status}</div>}
        <div className="card-grid">
          {summary.focus_queue.map((item) => (
            <div key={item} className="panel module-card">
              <div className="module-label">Drill</div>
              <h3>{item}</h3>
              <p>Complete this drill to unlock your next progression badge.</p>
              <div className="module-footer">
                <span className="module-intensity">Target</span>
                <Link className="btn primary" to="/session">
                  Run Scenario
                </Link>
              </div>
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
            <li>{String(scenario.learning_point ?? "Compare your action to the recommended line.")}</li>
          </ul>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Performance Gate</h2>
            <p>Unlock the next drill when you meet the threshold.</p>
          </div>
          <ul className="focus-list">
            {Array.isArray(scenario.recommended_actions) ? (
              scenario.recommended_actions.map((action) => <li key={String(action)}>{String(action)}</li>)
            ) : (
              <li>Complete the current spot and review the recommended action.</li>
            )}
          </ul>
          <Link className="btn ghost" to="/training">
            Back to Training
          </Link>
        </div>
      </section>
    </>
  );
}

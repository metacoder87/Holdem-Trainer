import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../components/Shell";

export default function Drill() {
  const { summary } = useOutletContext<ShellContext>();

  return (
    <>
      <section className="section">
        <div className="section-header">
          <h2>Guided Drill</h2>
          <p>Scenario-based reps tailored to your highest-priority leaks.</p>
        </div>
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
            <h2>Drill Instructions</h2>
            <p>Step-by-step guidance and hint system.</p>
          </div>
          <ul className="focus-list">
            <li>Review target range chart</li>
            <li>Play the scenario with timer enabled</li>
            <li>Compare your action to the EV baseline</li>
            <li>Repeat until consistency &gt; 80%</li>
          </ul>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Performance Gate</h2>
            <p>Unlock the next drill when you meet the threshold.</p>
          </div>
          <div className="chart-placeholder">
            <div className="chart-grid" />
            <div className="chart-label">Accuracy + speed tracking</div>
          </div>
          <Link className="btn ghost" to="/training">
            Back to Training
          </Link>
        </div>
      </section>
    </>
  );
}

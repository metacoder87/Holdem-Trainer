import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="section">
      <div className="panel">
        <div className="panel-header">
          <h2>Page Not Found</h2>
          <p>This route isn't wired yet. Jump back to the dashboard.</p>
        </div>
        <Link className="btn primary" to="/">
          Return Home
        </Link>
      </div>
    </section>
  );
}

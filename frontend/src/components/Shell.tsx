import { NavLink, Outlet } from "react-router-dom";
import type { SummaryResponse } from "../api/client";

export type ShellContext = {
  summary: SummaryResponse;
  activePlayer: string | null;
  setActivePlayer?: (player: string | null) => void;
};

type ShellProps = {
  summary: SummaryResponse;
  apiStatus: "checking" | "online" | "offline";
  activePlayer: string | null;
  setActivePlayer?: (player: string | null) => void;
};

function titleCase(value?: string | null) {
  if (!value) return "Rookie";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function Shell({ summary, apiStatus, activePlayer, setActivePlayer }: ShellProps) {
  return (
    <div className="app">
      <div className="glow-layer" />
      <div className="grid-layer" />

      <header className="top-bar fade-up">
        <NavLink to="/" className="brand">
          <div className="brand-mark">PH</div>
          <div className="brand-text">
            <div className="brand-name">PyHoldem Pro</div>
            <div className="brand-tag">Neon Training Lab</div>
          </div>
        </NavLink>
        <nav className="nav">
          <NavLink to="/games" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Play
          </NavLink>
          <NavLink to="/session" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Session
          </NavLink>
          <NavLink to="/training" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Training
          </NavLink>
          <NavLink to="/analytics" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Analytics
          </NavLink>
          <NavLink to="/replay" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Replay
          </NavLink>
          <NavLink to="/bankroll" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Bankroll
          </NavLink>
        </nav>
        <div className="top-status">
          <div className="player-pill">
            <span className="player-name">{activePlayer || summary.player.name}</span>
            <span className="player-rank">{titleCase(summary.player.skill_level)}</span>
          </div>
          <div className={`status-pill ${apiStatus}`}>API {apiStatus}</div>
        </div>
      </header>

      <main>
        <Outlet context={{ summary, activePlayer, setActivePlayer }} />
      </main>
    </div>
  );
}

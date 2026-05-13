import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { getHealth, getSummary, SummaryResponse } from "./api/client";
import Shell from "./components/Shell";

const Home = lazy(() => import("./pages/Home"));
const Training = lazy(() => import("./pages/Training"));
const Table = lazy(() => import("./pages/Table"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Replay = lazy(() => import("./pages/Replay"));
const ReplayDetail = lazy(() => import("./pages/ReplayDetail"));
const Session = lazy(() => import("./pages/Session"));
const Drill = lazy(() => import("./pages/Drill"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Bankroll = lazy(() => import("./pages/Bankroll"));
const Games = lazy(() => import("./pages/Games"));

function PageBoundary({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="page-loading">Loading...</div>}>{children}</Suspense>;
}

const emptySummary: SummaryResponse = {
  player: {
    name: "Guest",
    skill_level: "rookie",
    last_played: null
  },
  live_metrics: [
    { label: "VPIP", value: "0%", delta: "+0%", tone: "warn" },
    { label: "PFR", value: "0%", delta: "+0%", tone: "warn" },
    { label: "AGG", value: "0.0", delta: "+0.0", tone: "warn" },
    { label: "DEC", value: "0%", delta: "+0%", tone: "warn" }
  ],
  training_tracks: [],
  focus_queue: [],
  timeline: []
};

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );
  const [summary, setSummary] = useState<SummaryResponse>(emptySummary);
  const [activePlayer, setActivePlayer] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getHealth()
      .then(() => {
        if (active) setApiStatus("online");
      })
      .catch(() => {
        if (active) setApiStatus("offline");
      });

    return () => {
      active = false;
    };
  }, [activePlayer]);

  useEffect(() => {
    let active = true;

    getSummary(activePlayer || undefined)
      .then((value) => {
        if (!active) return;
        setSummary(value);
        if (!activePlayer && value.player?.name) {
          setActivePlayer(value.player.name);
        }
      })
      .catch(() => {
        if (!active) return;
      });

    return () => {
      active = false;
    };
  }, [activePlayer]);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Shell
              summary={summary}
              apiStatus={apiStatus}
              activePlayer={activePlayer}
              setActivePlayer={setActivePlayer}
            />
          }
        >
          <Route index element={<PageBoundary><Home /></PageBoundary>} />
          <Route path="games" element={<PageBoundary><Games /></PageBoundary>} />
          <Route path="table" element={<PageBoundary><Table /></PageBoundary>} />
          <Route path="training" element={<PageBoundary><Training /></PageBoundary>} />
          <Route path="training/drill" element={<PageBoundary><Drill /></PageBoundary>} />
          <Route path="analytics" element={<PageBoundary><Analytics /></PageBoundary>} />
          <Route path="replay" element={<PageBoundary><Replay /></PageBoundary>} />
          <Route path="replay/:handNumber" element={<PageBoundary><ReplayDetail /></PageBoundary>} />
          <Route path="session" element={<PageBoundary><Session /></PageBoundary>} />
          <Route path="bankroll" element={<PageBoundary><Bankroll /></PageBoundary>} />
          <Route path="*" element={<PageBoundary><NotFound /></PageBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

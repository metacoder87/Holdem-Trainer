import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { getHealth, getSummary, SummaryResponse } from "./api/client";
import Shell from "./components/Shell";
import {
  Home,
  Training,
  Table,
  Analytics,
  Replay,
  ReplayDetail,
  Session,
  Drill,
  NotFound,
  Bankroll,
  Games
} from "./pages";

const fallbackSummary: SummaryResponse = {
  player: {
    name: "Guest",
    skill_level: "rookie",
    last_played: null
  },
  live_metrics: [
    { label: "VPIP", value: "23%", delta: "+2%", tone: "good" },
    { label: "PFR", value: "19%", delta: "+1%", tone: "good" },
    { label: "AGG", value: "2.7", delta: "-0.2", tone: "warn" },
    { label: "DEC", value: "64%", delta: "+4%", tone: "good" }
  ],
  training_tracks: [
    {
      title: "Preflop Mastery",
      summary: "Ranges, position, open sizes, 3-bet defense",
      cadence: "Daily drills",
      intensity: "Core",
      progress: 62
    },
    {
      title: "Postflop Pressure",
      summary: "Board texture, sizing, multi-street planning",
      cadence: "Scenario lab",
      intensity: "Advanced",
      progress: 48
    },
    {
      title: "Tournament Edge",
      summary: "ICM, bubble play, stack depth, payout pressure",
      cadence: "Event prep",
      intensity: "Pro",
      progress: 35
    },
    {
      title: "Range vs Range",
      summary: "Equity, blockers, node lock reviews",
      cadence: "Solver review",
      intensity: "Expert",
      progress: 28
    }
  ],
  focus_queue: [
    "Button opens vs 3-bet",
    "Turn barrel frequency",
    "Blind defense sizing",
    "River bluff selectivity"
  ],
  focus_queue_items: [
    { id: null, label: "Button opens vs 3-bet" },
    { id: null, label: "Turn barrel frequency" },
    { id: null, label: "Blind defense sizing" },
    { id: null, label: "River bluff selectivity" }
  ],
  timeline: [
    { time: "10:12", label: "Hand 42", detail: "Missed thin value spot" },
    { time: "10:18", label: "Hand 43", detail: "Good fold vs polar river" },
    { time: "10:26", label: "Hand 44", detail: "Check-raise timing leak" }
  ]
};

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );
  const [summary, setSummary] = useState<SummaryResponse>(fallbackSummary);
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
  }, []);

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
          <Route index element={<Home />} />
          <Route path="games" element={<Games />} />
          <Route path="table" element={<Table />} />
          <Route path="training" element={<Training />} />
          <Route path="training/drill" element={<Drill />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="replay" element={<Replay />} />
          <Route path="replay/:handNumber" element={<ReplayDetail />} />
          <Route path="session" element={<Session />} />
          <Route path="bankroll" element={<Bankroll />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

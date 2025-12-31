import { useEffect, useMemo, useState } from "react";
import type { ShellContext } from "../components/Shell";
import { useOutletContext } from "react-router-dom";
import {
  createPlayer,
  getBankrollSummary,
  getPlayers,
  updateBankroll,
  type BankrollSummary,
  type PlayerSummary
} from "../api/client";

export default function Bankroll() {
  const { setActivePlayer, activePlayer } = useOutletContext<ShellContext>();
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [summary, setSummary] = useState<BankrollSummary | null>(null);
  const [selected, setSelected] = useState<PlayerSummary | null>(null);
  const [bankrollInput, setBankrollInput] = useState("");
  const [newName, setNewName] = useState("");
  const [newBankroll, setNewBankroll] = useState("10000");
  const [status, setStatus] = useState<string | null>(null);

  const refresh = () => {
    Promise.all([getPlayers(), getBankrollSummary()])
      .then(([playersResponse, summaryResponse]) => {
        setPlayers(playersResponse);
        setSummary(summaryResponse);
        if (selected) {
          const updated = playersResponse.find((p) => p.name === selected.name) || null;
          setSelected(updated);
          if (updated) {
            setBankrollInput(String(updated.bankroll));
          }
        }
      })
      .catch((err) => {
        setStatus(err.message || "Failed to load bankroll data");
      });
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!activePlayer || players.length === 0) return;
    const current = players.find((player) => player.name === activePlayer);
    if (current) {
      setSelected(current);
      setBankrollInput(String(current.bankroll));
    }
  }, [activePlayer, players]);

  const totalBankroll = useMemo(() => {
    return summary ? summary.total_bankroll.toLocaleString() : "0";
  }, [summary]);

  const handleSelect = (player: PlayerSummary) => {
    setSelected(player);
    setBankrollInput(String(player.bankroll));
    setActivePlayer?.(player.name);
    setStatus(null);
  };

  const handleUpdate = async () => {
    if (!selected) return;
    const value = Number(bankrollInput);
    if (Number.isNaN(value) || value < 0) {
      setStatus("Enter a valid bankroll value.");
      return;
    }
    try {
      await updateBankroll(selected.name, value);
      setStatus("Bankroll updated.");
      refresh();
    } catch (err) {
      if (err instanceof Error) {
        setStatus(err.message);
      }
    }
  };

  const handleCreate = async () => {
    const value = Number(newBankroll);
    if (!newName.trim() || Number.isNaN(value) || value <= 0) {
      setStatus("Enter a valid player name and bankroll.");
      return;
    }
    try {
      await createPlayer(newName.trim(), value);
      setNewName("");
      setNewBankroll("10000");
      setStatus("Player created.");
      refresh();
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
          <h2>Bankroll Manager</h2>
          <p>Track player funds and switch the active dashboard profile.</p>
        </div>
        <div className="bankroll-summary panel">
          <div>
            <div className="stat-label">Total Players</div>
            <div className="stat-value good">{summary?.total_players ?? 0}</div>
          </div>
          <div>
            <div className="stat-label">Total Bankroll</div>
            <div className="stat-value">${totalBankroll}</div>
          </div>
          <div>
            <div className="stat-label">Games Logged</div>
            <div className="stat-value">{summary?.total_games_played ?? 0}</div>
          </div>
        </div>
      </section>

      <section className="section split">
        <div className="panel">
          <div className="panel-header">
            <h2>Players</h2>
            <p>Select a player to update bankroll or set as active.</p>
          </div>
          <div className="bankroll-list">
            {players.map((player) => (
              <button
                key={player.name}
                className={`bankroll-item${selected?.name === player.name ? " active" : ""}`}
                type="button"
                onClick={() => handleSelect(player)}
              >
                <div>
                  <div className="bankroll-name">{player.name}</div>
                  <div className="bankroll-meta">{player.skill_level ?? "unranked"}</div>
                </div>
                <div className="bankroll-amount">${player.bankroll.toLocaleString()}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Update Bankroll</h2>
            <p>Set bankroll for the selected player.</p>
          </div>
          <div className="bankroll-form">
            <label>
              Player
              <input
                type="text"
                value={selected?.name ?? "Select a player"}
                readOnly
              />
            </label>
            <label>
              Bankroll
              <input
                type="number"
                value={bankrollInput}
                onChange={(event) => setBankrollInput(event.target.value)}
                placeholder="Enter new bankroll"
              />
            </label>
            <div className="hero-actions">
              <button className="btn primary" type="button" onClick={handleUpdate}>
                Save Bankroll
              </button>
              <button className="btn ghost" type="button" onClick={refresh}>
                Refresh
              </button>
            </div>
            {status && <div className="form-status">{status}</div>}
          </div>

          <div className="panel-header" style={{ marginTop: 24 }}>
            <h2>Create Player</h2>
            <p>Add a new profile to the bankroll roster.</p>
          </div>
          <div className="bankroll-form">
            <label>
              Name
              <input
                type="text"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="Player name"
              />
            </label>
            <label>
              Starting Bankroll
              <input
                type="number"
                value={newBankroll}
                onChange={(event) => setNewBankroll(event.target.value)}
                placeholder="10000"
              />
            </label>
            <button className="btn primary" type="button" onClick={handleCreate}>
              Create Player
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

import React, { useState, useEffect, useCallback } from "react";
import { API } from "./api.js";
import { C } from "./theme.js";
import { Badge, AgentBadge, GoogleBadge, NavTab, QuotaWarning } from "./components/shared.jsx";
import TracesPage from "./pages/TracesPage.jsx";
import OptimizerPage from "./pages/OptimizerPage.jsx";

function pageFromHash() {
  return window.location.hash === "#/optimizer" ? "optimizer" : "traces";
}

export default function App() {
  const [page, setPage] = useState(pageFromHash);
  const [runs, setRuns] = useState([]);
  const [live, setLive] = useState(false);
  const [health, setHealth] = useState(null);
  const [running, setRunning] = useState(null);

  const refreshRuns = useCallback(async () => {
    try {
      const [t, h] = await Promise.all([API.traces(), API.health()]);
      if (Array.isArray(t.runs)) setRuns(t.runs);
      setHealth(h);
      setLive(true);
    } catch {
      setLive(false);
      setRuns([]);
    }
  }, []);

  useEffect(() => {
    refreshRuns();
    const poll = setInterval(refreshRuns, 5000);
    return () => clearInterval(poll);
  }, [refreshRuns]);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: "100vh", fontFamily: "Inter, -apple-system, system-ui, sans-serif", fontSize: 13 }}>
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", height: 50, position: "sticky", top: 0, background: C.bg, zIndex: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: C.heading }}>TokenClock</span>
          <nav style={{ display: "flex", gap: 4 }}>
            <NavTab href="#/" active={page === "traces"}>Traces</NavTab>
            <NavTab href="#/optimizer" active={page === "optimizer"}>Optimizer</NavTab>
          </nav>
          <Badge color={live ? C.emerald : C.amber} bg={live ? C.okBg : "#1C1500"} border={live ? "#0C3018" : "#2A2000"}
            label={live ? "LIVE" : "NOT LIVE"} title={live ? "Connected to server.py" : "Server not reachable"} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <AgentBadge agent={health?.agent} />
          <GoogleBadge g={health?.google} />
        </div>
      </div>

      <div style={{ padding: 24 }}>
        <QuotaWarning health={health} />
        {page === "optimizer" ? (
          <OptimizerPage health={health} live={live} running={running} setRunning={setRunning} onRefresh={refreshRuns} />
        ) : (
          <TracesPage live={live} running={running} setRunning={setRunning} refreshRuns={refreshRuns} runs={runs} setRuns={setRuns} />
        )}
      </div>
    </div>
  );
}

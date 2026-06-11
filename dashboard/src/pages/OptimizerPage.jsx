import React, { useState, useEffect, useCallback } from "react";
import { API } from "../api.js";
import { C, PROMPT_STORAGE_KEY, styles } from "../theme.js";
import { OptimizationRun } from "../components/OptimizerRun.jsx";

export default function OptimizerPage({ health, live, running, setRunning, onRefresh }) {
  const [prompt, setPrompt] = useState("");
  const [msg, setMsg] = useState("");
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [clearMsg, setClearMsg] = useState("");
  const busy = running !== null;

  const loadHistory = useCallback(async () => {
    try {
      const data = await API.optimizations();
      if (Array.isArray(data.runs)) setHistory(data.runs);
    } catch { /* keep previous */ }
  }, []);

  useEffect(() => {
    const queued = sessionStorage.getItem(PROMPT_STORAGE_KEY);
    if (queued) {
      setPrompt(queued);
      sessionStorage.removeItem(PROMPT_STORAGE_KEY);
    }
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    const id = setInterval(loadHistory, 8000);
    return () => clearInterval(id);
  }, [loadHistory]);

  async function runOptimize() {
    if (busy || !prompt.trim()) return;
    setRunning("optimize");
    setMsg("");
    setLatest(null);
    try {
      const { ok, data } = await API.optimize({ prompt: prompt.trim() });
      if (!ok || !data.ok) {
        setMsg(data?.error || "Optimization failed.");
      } else {
        setLatest(data);
        setMsg("Done — compare original vs optimized below.");
        await loadHistory();
        onRefresh?.();
      }
    } catch {
      setMsg("Could not reach the server. Is server.py running?");
    } finally {
      setRunning(null);
    }
  }

  async function clearHistory() {
    if (busy || !live) return;
    if (!window.confirm("Clear all optimization run history?")) return;
    setClearMsg("");
    try {
      const { ok, data } = await API.clearOptimizations();
      if (!ok || !data.ok) setClearMsg(data?.error || "Could not clear.");
      else {
        setHistory([]);
        setLatest(null);
        setClearMsg(`Cleared ${data.removed} optimization run(s).`);
      }
    } catch {
      setClearMsg("Could not reach the server.");
    }
  }

  const agentOk = health?.agent?.adk_available;

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: C.heading, margin: "0 0 6px" }}>Prompt optimizer</h1>
        <p style={{ fontSize: 12.5, color: C.muted, margin: 0, lineHeight: 1.55, maxWidth: 640 }}>
          Gemini agent measures your prompt, rewrites it for fewer tokens and lower latency, then verifies savings.
          Each run is saved below with a side-by-side comparison.
        </p>
      </div>

      {!agentOk && live && (
        <div style={{ marginBottom: 16, padding: "11px 16px", background: C.errBg, border: "1px solid #320A14", borderRadius: 9, fontSize: 12.5, color: C.red }}>
          Agent not installed — run <code>pip install -r requirements.txt</code> in the backend venv.
        </div>
      )}

      <div style={{ ...styles.card, padding: "16px 18px", marginBottom: 24 }}>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Paste a verbose prompt to optimize…"
          disabled={busy}
          rows={4}
          style={{
            width: "100%", background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8,
            color: C.text, padding: "10px 12px", fontSize: 12.5, outline: "none", resize: "vertical",
            fontFamily: "inherit", marginBottom: 12, boxSizing: "border-box",
          }}
        />
        <button onClick={runOptimize} disabled={busy || !prompt.trim() || !agentOk}
          style={{
            background: (busy || !prompt.trim() || !agentOk) ? "#0E2233" : C.emerald,
            color: (busy || !prompt.trim() || !agentOk) ? C.muted : "#001019",
            border: "none", borderRadius: 8, padding: "9px 20px", fontSize: 12.5, fontWeight: 600,
            cursor: (busy || !prompt.trim() || !agentOk) ? "default" : "pointer",
          }}>
          {running === "optimize" ? <><span className="spinner" />Optimizing…</> : "Optimize prompt"}
        </button>
        {msg && <div style={{ marginTop: 10, fontSize: 12, color: C.mutedMid }}>{msg}</div>}
        {latest && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: C.mutedMid, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Latest run</div>
            <OptimizationRun run={{
              id: latest.id,
              timestamp: latest.timestamp,
              original_prompt: latest.original_prompt,
              optimized_prompt: latest.optimized_prompt,
              metrics: latest.metrics,
              report: latest.report,
            }} defaultOpen />
          </div>
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 500, color: C.mutedMid, textTransform: "uppercase", letterSpacing: "0.09em" }}>
          Optimization history · {history.length}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {clearMsg && <span style={{ fontSize: 11, color: C.mutedMid }}>{clearMsg}</span>}
          <button onClick={clearHistory} disabled={busy || !live || history.length === 0}
            style={{
              background: "transparent", color: (busy || !live || !history.length) ? C.muted : C.red,
              border: `1px solid ${(busy || !live || !history.length) ? C.border : "#3A1020"}`,
              borderRadius: 6, padding: "5px 10px", fontSize: 11, cursor: (busy || !live || !history.length) ? "default" : "pointer",
            }}>
            Clear history
          </button>
        </div>
      </div>

      {history.length === 0 ? (
        <div style={{ ...styles.card, padding: "32px", textAlign: "center", color: C.muted, fontSize: 12.5 }}>
          No optimization runs yet. Submit a prompt above.
        </div>
      ) : (
        [...history].reverse().map(run => (
          <OptimizationRun key={run.id} run={run} />
        ))
      )}
    </div>
  );
}

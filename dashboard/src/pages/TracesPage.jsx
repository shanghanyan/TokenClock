import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar
} from "recharts";
import { API } from "../api.js";
import { C, STATUS_COLOR, fmtMs, fmtTime, percentile, styles, PROMPT_STORAGE_KEY } from "../theme.js";

const runStatus = r => (r.success ? "ok" : r.quota ? "quota" : "error");

function WaterfallBar({ run, maxMs }) {
  const fillFrac = Math.max(0.04, run.totalMs / maxMs);
  const total = run.totalMs || 1;
  const prepW = (run.prepMs / total) * 100;
  const postW = (run.postMs / total) * 100;
  return (
    <div style={{ flex: 1, height: 8, background: "#0A141F", borderRadius: 4, overflow: "hidden", position: "relative" }}>
      <div style={{ width: `${fillFrac * 100}%`, height: "100%", display: "flex", position: "absolute", left: 0, top: 0 }}>
        {run.success ? (
          <>
            <div style={{ width: `${prepW}%`, background: C.violet, flexShrink: 0 }} />
            <div style={{ flex: 1, background: C.cyan }} />
            <div style={{ width: `${postW}%`, background: C.emerald, flexShrink: 0 }} />
          </>
        ) : (
          <div style={{ width: "100%", background: run.quota ? "#2A2008" : "#3A1020", opacity: 0.8 }} />
        )}
      </div>
    </div>
  );
}

function PromptCell({ run }) {
  const orig = run.originalPrompt;
  const opt = run.optimizedPrompt;
  if (orig && opt) {
    return (
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 9, color: C.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>Original</div>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }} title={orig}>{orig}</div>
        <div style={{ fontSize: 9, color: C.emerald, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: 6, marginBottom: 2 }}>Optimized</div>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12, color: C.emerald }} title={opt}>{opt}</div>
      </div>
    );
  }
  const preview = run.promptPreview || run.prompt;
  return (
    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={run.prompt}>{preview}</div>
  );
}

function TrashButton({ onClick, disabled }) {
  return (
    <button
      type="button"
      title="Delete run"
      disabled={disabled}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        background: "transparent", border: "none", padding: 4, cursor: disabled ? "default" : "pointer",
        color: disabled ? C.muted : C.red, display: "flex", alignItems: "center", justifyContent: "center",
        opacity: disabled ? 0.4 : 0.85,
      }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 6h18" />
        <path d="M8 6V4h8v2" />
        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
        <path d="M10 11v6" />
        <path d="M14 11v6" />
      </svg>
    </button>
  );
}

function runRoleLabel(run) {
  if (run.optimizationRole === "baseline" || run.optimizationRole === "optimized") return "compare";
  if (run.originalPrompt && run.optimizedPrompt) return "compare";
  return "test";
}

function RoleBadge({ run }) {
  const label = runRoleLabel(run);
  const cfg = label === "compare"
    ? { color: C.violet, bg: C.violetBg }
    : { color: C.cyan, bg: C.cyanBg };
  return (
    <span style={{
      fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em",
      color: cfg.color, background: cfg.bg, border: `1px solid ${C.border}`, borderRadius: 4, padding: "2px 6px",
    }}>{label}</span>
  );
}

function RunDetail({ run }) {
  const orig = run.originalPrompt || run.prompt;
  const opt = run.optimizedPrompt;
  const showPair = orig && opt;
  const tps = run.success && run.inferenceMs > 0 ? (run.completionTokens / (run.inferenceMs / 1000)).toFixed(1) : null;
  return (
    <div>
      {showPair && (
        <div style={{ marginBottom: 20 }}>
          <div style={styles.detailLabel}>Optimization comparison</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderLeft: `3px solid ${C.violet}`, borderRadius: 8, padding: "10px 12px", fontSize: 12, lineHeight: 1.5 }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 6 }}>ORIGINAL</div>
              {orig}
            </div>
            <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderLeft: `3px solid ${C.emerald}`, borderRadius: 8, padding: "10px 12px", fontSize: 12, lineHeight: 1.5 }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 6 }}>OPTIMIZED</div>
              {opt}
            </div>
          </div>
          {run.optimizationSavings && (
            <div style={{ marginTop: 8, fontSize: 11, color: C.emerald, fontFamily: "monospace" }}>
              Saved {run.optimizationSavings.tokens} tokens ({run.optimizationSavings.tokens_pct}%), {fmtMs(run.optimizationSavings.total_ms)} latency
            </div>
          )}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
      <div>
        <div style={styles.detailLabel}>Stage breakdown</div>
        {[
          { name: "Prompt prep", ms: run.prepMs, color: C.violet },
          { name: "Inference", ms: run.inferenceMs, color: C.cyan },
          { name: "Post-process", ms: run.postMs, color: C.emerald },
          { name: "Total", ms: run.totalMs, color: C.text },
        ].map(({ name, ms, color }) => (
          <div key={name} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: C.muted }}>{name}</span>
            <span style={{ fontFamily: "monospace", fontSize: 12, color: ms > 0 ? color : C.muted }}>{ms > 0 ? fmtMs(ms) : "—"}</span>
          </div>
        ))}
        {tps && <div style={{ marginTop: 10, padding: "7px 10px", background: C.cyanBg, borderRadius: 6, fontSize: 11, color: C.muted }}>Throughput: <span style={{ color: C.cyan, fontFamily: "monospace" }}>{tps} tok/s</span></div>}
        {run.errorMsg && <div style={{ marginTop: 10, padding: "10px 12px", background: run.quota ? "#1C1500" : C.errBg, borderRadius: 6, fontSize: 11, color: run.quota ? C.amber : C.red, fontFamily: "monospace", wordBreak: "break-word" }}>{run.errorMsg}</div>}
      </div>
      <div>
        <div style={styles.detailLabel}>Token usage</div>
        {run.success && run.totalTokens > 0 ? (
          <>
            {[{ label: "Prompt", val: run.promptTokens, color: C.violet }, { label: "Completion", val: run.completionTokens, color: C.cyan }, { label: "Total", val: run.totalTokens, color: C.text }].map(({ label, val, color }) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.muted }}>{label}</span>
                <span style={{ fontFamily: "monospace", fontSize: 12, color }}>{val}</span>
              </div>
            ))}
          </>
        ) : <div style={{ fontSize: 12, color: C.muted }}>No token data.</div>}
      </div>
      </div>
    </div>
  );
}

const COLS = [
  { label: "#", key: null, w: 36 },
  { label: "Time", key: "timestamp", w: 82 },
  { label: "Role", key: "optimizationRole", w: 72 },
  { label: "Prompt", key: "prompt", w: null },
  { label: "Model", key: "model", w: 120 },
  { label: "Tokens", key: "totalTokens", w: 64 },
  { label: "Status", key: "success", w: 64 },
  { label: "Pipeline", key: "totalMs", w: 180 },
  { label: "", key: null, w: 40 },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const status = payload[0]?.payload?.status;
  return (
    <div style={{ background: C.card, border: `1px solid ${C.borderMid}`, borderRadius: 8, padding: "10px 14px", fontSize: 12 }}>
      <div style={{ color: C.muted, marginBottom: 4 }}>Run {label}{status ? ` · ${status}` : ""}</div>
      {payload.map(p => <div key={p.name} style={{ color: p.color || C.text }}>{p.name === "ms" ? fmtMs(p.value) : `${p.value} tokens`}</div>)}
    </div>
  );
};

function sendToOptimizer(text) {
  sessionStorage.setItem(PROMPT_STORAGE_KEY, text);
  window.location.hash = "#/optimizer";
}

export default function TracesPage({ live, running, setRunning, refreshRuns, runs, setRuns }) {
  const [promptText, setPromptText] = useState("");
  const [runMsg, setRunMsg] = useState("");
  const [clearMsg, setClearMsg] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [sortKey, setSortKey] = useState("timestamp");
  const [sortDir, setSortDir] = useState("asc");
  const [hovered, setHovered] = useState(null);
  const busy = running !== null;

  async function runTest(mode) {
    if (running) return;
    setRunning(mode);
    setRunMsg("");
    try {
      const { ok, data } = await API.run(mode === "single" ? { mode, prompt: promptText } : { mode });
      if (!ok || !data.ok) setRunMsg(data?.error || "Run failed.");
      else {
        const okN = data.results.filter(r => r.ok).length;
        setRunMsg(`Completed ${data.results.length} prompt(s): ${okN} ok, ${data.results.length - okN} failed.`);
        if (mode === "single") setPromptText("");
      }
    } catch {
      setRunMsg("Could not reach the server. Is server.py running?");
    } finally {
      setRunning(null);
      refreshRuns();
    }
  }

  async function deleteRun(traceId) {
    if (running || !live) return;
    setClearMsg("");
    try {
      const { ok, data } = await API.deleteTrace(traceId);
      if (!ok || !data.ok) setClearMsg(data?.error || "Could not delete run.");
      else {
        setRuns(prev => prev.filter(r => r.traceId !== traceId));
        if (expandedId === traceId) setExpandedId(null);
      }
    } catch {
      setClearMsg("Could not reach the server.");
    }
    refreshRuns();
  }

  async function clearHistory() {
    if (running || !live) return;
    if (!window.confirm("Clear all past prompt trace data?")) return;
    setClearMsg("");
    try {
      const { ok, data } = await API.clearTraces();
      if (!ok || !data.ok) setClearMsg(data?.error || "Could not clear.");
      else {
        setRuns([]);
        setExpandedId(null);
        setClearMsg(`Cleared ${data.removed} trace run(s).`);
      }
    } catch {
      setClearMsg("Could not reach the server.");
    }
    refreshRuns();
  }

  const sorted = useMemo(() => [...runs].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
    if (av < bv) return sortDir === "asc" ? -1 : 1;
    if (av > bv) return sortDir === "asc" ? 1 : -1;
    return 0;
  }), [runs, sortKey, sortDir]);

  const stats = useMemo(() => {
    const counted = runs.filter(r => !r.quota);
    const succ = runs.filter(r => r.success);
    const lats = counted.map(r => r.totalMs);
    return {
      total: runs.length,
      quotaCount: runs.length - counted.length,
      successRate: counted.length ? Math.round(succ.length / counted.length * 100) : 0,
      avgMs: lats.length ? lats.reduce((a, b) => a + b, 0) / lats.length : 0,
      p95Ms: percentile(lats, 95),
      totalTokens: succ.reduce((a, r) => a + r.totalTokens, 0),
    };
  }, [runs]);

  const maxMs = useMemo(() => Math.max(...runs.map(r => r.totalMs), 1), [runs]);
  const lineData = useMemo(() => runs.map((r, i) => ({ idx: i + 1, ms: Math.round(r.totalMs), status: runStatus(r) })), [runs]);
  const barData = useMemo(() => runs.map((r, i) => ({ idx: i + 1, tokens: r.totalTokens })).filter(d => d.tokens > 0), [runs]);
  const srColor = stats.successRate >= 80 ? C.emerald : stats.successRate >= 50 ? C.amber : C.red;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 14, marginBottom: 20 }}>
        <div style={{ ...styles.card, padding: "16px 18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.heading, marginBottom: 4 }}>Automatic test</div>
            <div style={{ fontSize: 11.5, color: C.muted, lineHeight: 1.5 }}>Runs the built-in benchmark prompts.</div>
          </div>
          <button onClick={() => runTest("auto")} disabled={busy}
            style={{ marginTop: 14, background: busy ? "#0E2233" : C.cyan, color: busy ? C.muted : "#001019", border: "none", borderRadius: 8, padding: "9px 0", fontSize: 12.5, fontWeight: 600, cursor: busy ? "default" : "pointer" }}>
            {running === "auto" ? <><span className="spinner" />Running…</> : "Run automatic test"}
          </button>
        </div>
        <div style={{ ...styles.card, padding: "16px 18px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.heading, marginBottom: 4 }}>Self test</div>
          <div style={{ fontSize: 11.5, color: C.muted, lineHeight: 1.5, marginBottom: 10 }}>Trace your own prompt end-to-end.</div>
          <input value={promptText} onChange={e => setPromptText(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && promptText.trim() && !busy) runTest("single"); }}
            placeholder="Type a prompt and press Enter…" disabled={busy}
            style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, padding: "9px 12px", fontSize: 12.5, outline: "none", boxSizing: "border-box" }} />
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            <button onClick={() => runTest("single")} disabled={busy || !promptText.trim()}
              style={{ background: (busy || !promptText.trim()) ? "#0E2233" : C.violet, color: (busy || !promptText.trim()) ? C.muted : "#0A0414", border: "none", borderRadius: 8, padding: "9px 20px", fontSize: 12.5, fontWeight: 600, cursor: (busy || !promptText.trim()) ? "default" : "pointer" }}>
              {running === "single" ? <><span className="spinner" />Running…</> : "Run prompt"}
            </button>
            {promptText.trim() && (
              <button type="button" onClick={() => sendToOptimizer(promptText)} disabled={busy}
                style={{ background: "transparent", color: C.emerald, border: `1px solid ${C.border}`, borderRadius: 8, padding: "9px 16px", fontSize: 12.5, cursor: busy ? "default" : "pointer" }}>
                Open in optimizer →
              </button>
            )}
          </div>
        </div>
      </div>
      {runMsg && <div style={{ marginTop: -8, marginBottom: 18, fontSize: 12, color: C.mutedMid }}>{runMsg}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
        {[
          { label: "Runs", value: stats.total, color: C.heading, sub: stats.quotaCount ? `${stats.quotaCount} quota-skipped` : null },
          { label: "Success rate", value: `${stats.successRate}%`, color: srColor, sub: "excl. quota" },
          { label: "Avg latency", value: fmtMs(stats.avgMs), color: C.cyan, sub: null },
          { label: "p95 latency", value: fmtMs(stats.p95Ms), color: C.amber, sub: null },
          { label: "Total tokens", value: stats.totalTokens.toLocaleString(), color: C.violet, sub: null },
        ].map(({ label, value, color, sub }) => (
          <div key={label} style={{ ...styles.card, padding: "14px 18px" }}>
            <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 7 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, color, fontFamily: "monospace" }}>{value}</div>
            {sub && <div style={{ fontSize: 9.5, color: C.muted, marginTop: 5 }}>{sub}</div>}
          </div>
        ))}
      </div>

      <div style={{ ...styles.card, overflow: "hidden", marginBottom: 18 }}>
        <div style={{ padding: "11px 18px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: C.mutedMid, textTransform: "uppercase", letterSpacing: "0.09em" }}>Runs · {runs.length}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {clearMsg && <span style={{ fontSize: 11, color: C.mutedMid }}>{clearMsg}</span>}
            <button onClick={clearHistory} disabled={busy || !live || runs.length === 0}
              style={{ background: "transparent", color: (busy || !live || !runs.length) ? C.muted : C.red, border: `1px solid ${C.border}`, borderRadius: 6, padding: "5px 10px", fontSize: 11, cursor: (busy || !live || !runs.length) ? "default" : "pointer" }}>
              Clear run data
            </button>
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
            <thead>
              <tr>
                {COLS.map(({ label, key, w }) => (
                  <th key={label} onClick={() => { if (!key) return; if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc"); else { setSortKey(key); setSortDir("asc"); } }}
                    style={{ ...styles.thCell, width: w ?? "auto" }}>
                    {label}{key && sortKey === key && <span style={{ color: C.cyan, marginLeft: 4 }}>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 && <tr><td colSpan={9} style={{ ...styles.tdCell, textAlign: "center", color: C.muted, padding: "28px 0" }}>No runs yet.</td></tr>}
              {sorted.map((run, i) => {
                const isExpanded = expandedId === run.traceId;
                return (
                  <React.Fragment key={run.traceId}>
                    <tr onClick={() => setExpandedId(isExpanded ? null : run.traceId)}
                      onMouseEnter={() => setHovered(run.traceId)} onMouseLeave={() => setHovered(null)}
                      style={{ cursor: "pointer", background: isExpanded ? "#0D1B2E" : hovered === run.traceId ? "#0B1826" : "transparent", borderBottom: `1px solid ${C.border}` }}>
                      <td style={{ ...styles.tdCell, color: C.muted, fontFamily: "monospace", fontSize: 11 }}>{i + 1}</td>
                      <td style={{ ...styles.tdCell, fontFamily: "monospace", fontSize: 11, color: C.muted }}>{fmtTime(run.timestamp)}</td>
                      <td style={styles.tdCell}><RoleBadge run={run} /></td>
                      <td style={{ ...styles.tdCell, maxWidth: 280 }}><PromptCell run={run} /></td>
                      <td style={{ ...styles.tdCell, fontFamily: "monospace", fontSize: 11, color: C.muted }}>{run.model}</td>
                      <td style={{ ...styles.tdCell, fontFamily: "monospace", fontSize: 12 }}>{run.totalTokens || "—"}</td>
                      <td style={styles.tdCell}><span style={{ fontSize: 10, fontWeight: 600, color: STATUS_COLOR[runStatus(run)] }}>{runStatus(run).toUpperCase()}</span></td>
                      <td style={{ ...styles.tdCell, paddingRight: 8 }}><WaterfallBar run={run} maxMs={maxMs} /></td>
                      <td style={{ ...styles.tdCell, width: 40, paddingRight: 12 }}>
                        <TrashButton onClick={() => deleteRun(run.traceId)} disabled={busy || !live} />
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr><td colSpan={9} style={{ padding: "16px 22px", background: C.cardAlt, borderBottom: `1px solid ${C.border}` }}><RunDetail run={run} /></td></tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={{ ...styles.card, padding: "16px 20px 12px" }}>
          <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Latency over time</span>
            <span style={{ display: "flex", gap: 10, textTransform: "none", letterSpacing: 0, fontWeight: 400 }}>
              {[["ok", "ok"], ["quota", "quota"], ["error", "error"]].map(([k, lbl]) => (
                <span key={k} style={{ display: "flex", alignItems: "center", gap: 4, color: C.muted }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: STATUS_COLOR[k], display: "inline-block" }} />{lbl}
                </span>
              ))}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={lineData} margin={{ top: 4, right: 10, bottom: 16, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="idx" stroke={C.border} tick={{ fontSize: 10, fill: C.muted }} />
              <YAxis stroke={C.border} tick={{ fontSize: 10, fill: C.muted }} tickFormatter={fmtMs} width={46} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="ms" stroke={C.cyan} strokeWidth={1.5}
                dot={(props) => {
                  const { cx, cy, index } = props;
                  const d = lineData[index];
                  return <circle key={index} cx={cx} cy={cy} r={5} fill={STATUS_COLOR[d?.status] || C.cyan} stroke={C.bg} strokeWidth={1.5} />;
                }}
                activeDot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={{ ...styles.card, padding: "16px 20px 12px" }}>
          <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", marginBottom: 14 }}>Tokens</div>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={barData} margin={{ top: 4, right: 10, bottom: 16, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="idx" stroke={C.border} tick={{ fontSize: 10, fill: C.muted }} />
                <YAxis stroke={C.border} tick={{ fontSize: 10, fill: C.muted }} width={40} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="tokens" fill={C.violet} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontSize: 12 }}>No token data yet.</div>}
        </div>
      </div>
    </div>
  );
}

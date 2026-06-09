import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar
} from "recharts";

const C = {
  bg: "#070C17",
  card: "#0C1522",
  cardAlt: "#091320",
  border: "#162035",
  borderMid: "#1E2E45",
  text: "#C8D8E8",
  heading: "#E4EEF8",
  muted: "#435A72",
  mutedMid: "#56718A",
  cyan: "#38BDF8",
  violet: "#B48FFF",
  emerald: "#34D39A",
  red: "#FB7185",
  amber: "#FBBF24",
  errBg: "#1A080D",
  okBg: "#071510",
  cyanBg: "#071B28",
  violetBg: "#120C1F",
};

// Offline fallback so the page still renders if the API isn't reachable.
const SAMPLE_RUNS = [
  {
    traceId: "tr001", timestamp: "2025-06-08T09:45:12.000Z",
    prompt: "What are the best practices for writing async Python code?",
    model: "gemini-2.5-flash", success: true, quota: false, errorMsg: null,
    totalMs: 8200, inferenceMs: 8199.3, prepMs: 0.11, postMs: 0.09,
    totalTokens: 380, promptTokens: 11, completionTokens: 369
  },
  {
    traceId: "tr002", timestamp: "2025-06-08T09:51:33.000Z",
    prompt: "Write a haiku about recursion in programming.",
    model: "gemini-2.5-flash", success: true, quota: false, errorMsg: null,
    totalMs: 8500, inferenceMs: 8499.2, prepMs: 0.08, postMs: 0.07,
    totalTokens: 195, promptTokens: 8, completionTokens: 187
  },
  {
    traceId: "tr003", timestamp: "2025-06-08T09:55:48.000Z",
    prompt: "Summarize the history of the internet in one paragraph.",
    model: "gemini-2.5-flash", success: false, quota: false,
    errorMsg: "503 UNAVAILABLE: This model is currently experiencing high demand.",
    totalMs: 27835, inferenceMs: 27834.1, prepMs: 0.10, postMs: 0,
    totalTokens: 0, promptTokens: 10, completionTokens: 0
  },
  {
    traceId: "tr004", timestamp: "2025-06-08T09:58:20.000Z",
    prompt: "Write a detailed comparison of REST vs GraphQL APIs.",
    model: "gemini-2.5-flash", success: false, quota: true,
    errorMsg: "429 RESOURCE_EXHAUSTED: You exceeded your current quota.",
    totalMs: 38009, inferenceMs: 38008.4, prepMs: 0.15, postMs: 0,
    totalTokens: 0, promptTokens: 18, completionTokens: 0
  },
];

// A run is one of: ok (success) | quota (429, infra limit) | error (other failure).
const runStatus = r => (r.success ? "ok" : r.quota ? "quota" : "error");
const STATUS_COLOR = { ok: C.cyan, quota: C.amber, error: C.red };

const fmtMs = v => {
  if (v >= 1000) return `${(v / 1000).toFixed(2)}s`;
  return `${Math.round(v)}ms`;
};
const fmtTime = v => new Date(v).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

function percentile(arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const idx = (p / 100) * (s.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return s[lo] + (idx - lo) * ((s[hi] ?? s[lo]) - s[lo]);
}

function WaterfallBar({ run, maxMs }) {
  const fillFrac = Math.max(0.04, run.totalMs / maxMs);
  const total = run.totalMs || 1;
  const prepW = (run.prepMs / total) * 100;
  const postW = (run.postMs / total) * 100;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, width: "100%" }}>
      <div style={{ flex: 1, height: 8, background: "#0A141F", borderRadius: 4, overflow: "hidden", position: "relative" }}>
        <div style={{ width: `${fillFrac * 100}%`, height: "100%", display: "flex", position: "absolute", left: 0, top: 0 }}>
          {run.success ? (
            <>
              <div style={{ width: `${prepW}%`, background: C.violet, flexShrink: 0, minWidth: run.prepMs > 0.05 ? 1 : 0 }} />
              <div style={{ flex: 1, background: C.cyan }} />
              <div style={{ width: `${postW}%`, background: C.emerald, flexShrink: 0, minWidth: run.postMs > 0.05 ? 1 : 0 }} />
            </>
          ) : (
            <div style={{ width: "100%", background: run.quota ? "#2A2008" : "#3A1020", opacity: 0.8 }} />
          )}
        </div>
      </div>
    </div>
  );
}

function RunDetail({ run }) {
  const tps = run.success && run.inferenceMs > 0
    ? (run.completionTokens / (run.inferenceMs / 1000)).toFixed(1)
    : null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
      <div>
        <div style={styles.detailLabel}>Stage breakdown</div>
        {[
          { name: "Prompt prep", ms: run.prepMs, color: C.violet },
          { name: "Inference", ms: run.inferenceMs, color: C.cyan },
          { name: "Post-process", ms: run.postMs, color: C.emerald },
          { name: "Total", ms: run.totalMs, color: C.text },
        ].map(({ name, ms, color }) => (
          <div key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: C.muted }}>{name}</span>
            <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: ms > 0 ? color : C.muted }}>
              {ms > 0 ? fmtMs(ms) : "—"}
            </span>
          </div>
        ))}
        {tps && (
          <div style={{ marginTop: 10, padding: "7px 10px", background: C.cyanBg, borderRadius: 6, fontSize: 11, color: C.muted }}>
            Throughput: <span style={{ color: C.cyan, fontFamily: "monospace" }}>{tps} tok/s</span>
          </div>
        )}
        {run.errorMsg && (
          <div style={{ marginTop: 10, padding: "10px 12px", background: run.quota ? "#1C1500" : C.errBg, border: `1px solid ${run.quota ? "#2A2000" : "#2A0A12"}`, borderRadius: 6, fontSize: 11, color: run.quota ? C.amber : C.red, fontFamily: "ui-monospace, monospace", wordBreak: "break-word" }}>
            {run.errorMsg}
          </div>
        )}
      </div>
      <div>
        <div style={styles.detailLabel}>Token usage</div>
        {run.success && run.totalTokens > 0 ? (
          <>
            {[
              { label: "Prompt", val: run.promptTokens, color: C.violet },
              { label: "Completion", val: run.completionTokens, color: C.cyan },
              { label: "Total", val: run.totalTokens, color: C.text },
            ].map(({ label, val, color }) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.muted }}>{label}</span>
                <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color }}>{val}</span>
              </div>
            ))}
            <div style={{ marginTop: 8, height: 6, borderRadius: 3, overflow: "hidden", background: "#0A141F", display: "flex" }}>
              <div style={{ width: `${(run.promptTokens / run.totalTokens) * 100}%`, background: C.violet }} />
              <div style={{ flex: 1, background: C.cyan }} />
            </div>
          </>
        ) : (
          <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>No token data — request failed before completion.</div>
        )}
      </div>
    </div>
  );
}

const styles = {
  detailLabel: { fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 },
  thCell: { padding: "8px 14px", textAlign: "left", color: C.muted, fontWeight: 400, fontSize: 10, letterSpacing: "0.09em", textTransform: "uppercase", cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", borderBottom: `1px solid ${C.border}` },
  tdCell: { padding: "10px 14px" },
  card: { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10 },
};

const COLS = [
  { label: "#", key: null, w: 36 },
  { label: "Time", key: "timestamp", w: 82 },
  { label: "Prompt", key: "prompt", w: null },
  { label: "Model", key: "model", w: 138 },
  { label: "Tokens", key: "totalTokens", w: 70 },
  { label: "Status", key: "success", w: 64 },
  { label: "Pipeline", key: "totalMs", w: 240 },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.card, border: `1px solid ${C.borderMid}`, borderRadius: 8, padding: "10px 14px", fontSize: 12 }}>
      <div style={{ color: C.muted, marginBottom: 4 }}>Run {label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color || C.text }}>
          {p.name === "ms" ? fmtMs(p.value) : `${p.value} tokens`}
        </div>
      ))}
    </div>
  );
};

function Badge({ color, bg, border, label, title }) {
  return (
    <span title={title} style={{
      display: "inline-flex", alignItems: "center", gap: 6, background: bg, color,
      border: `1px solid ${border}`, borderRadius: 6, fontSize: 11, padding: "4px 9px",
      fontWeight: 500, whiteSpace: "nowrap", cursor: "default"
    }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

function DynatraceBadge({ dt }) {
  if (!dt) return null;
  let s;
  if (dt.status === "healthy") {
    s = dt.exporting
      ? { color: C.emerald, bg: C.okBg, border: "#0C3018", label: "Dynatrace: Exporting" }
      : { color: C.emerald, bg: C.okBg, border: "#0C3018", label: "Dynatrace: Ready (export off)" };
  } else {
    s = {
      needs_access: { color: C.amber, bg: "#1C1500", border: "#2A2000", label: "Dynatrace: Needs access" },
      not_configured: { color: C.mutedMid, bg: "#0A1018", border: C.border, label: "Dynatrace: Not configured" },
      error: { color: C.red, bg: C.errBg, border: "#320A14", label: "Dynatrace: Error" },
    }[dt.status] || { color: C.red, bg: C.errBg, border: "#320A14", label: "Dynatrace: Error" };
  }
  const title = [dt.message, dt.export_enabled ? "Export: enabled" : "Export: disabled"]
    .filter(Boolean).join(" · ");
  return <Badge {...s} title={title} />;
}

function GoogleBadge({ g }) {
  if (!g) return null;
  const exhausted = g.remaining_total === 0;
  const cfg = exhausted
    ? { color: C.red, bg: C.errBg, border: "#320A14", label: "Google: quota exhausted" }
    : g.warning
      ? { color: C.amber, bg: "#1C1500", border: "#2A2000", label: `Google: low (${g.remaining_total} left)` }
      : { color: C.emerald, bg: C.okBg, border: "#0C3018", label: `Google: ${g.remaining_total} left` };
  const title = g.keys?.map(k => `${k.id} ${k.fingerprint}: ${k.remaining}/${k.limit} left${k.exhausted ? " (exhausted)" : ""}`).join("\n");
  return <Badge {...cfg} title={title} />;
}

const API = {
  traces: () => fetch("/api/traces").then(r => r.json()),
  health: () => fetch("/api/health").then(r => r.json()),
  run: (body) => fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  }).then(async r => ({ ok: r.ok, data: await r.json() })),
};

export default function App() {
  const [runs, setRuns] = useState(SAMPLE_RUNS);
  const [live, setLive] = useState(false);
  const [health, setHealth] = useState(null);
  const [running, setRunning] = useState(null);     // "auto" | "single" | null
  const [promptText, setPromptText] = useState("");
  const [runMsg, setRunMsg] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [sortKey, setSortKey] = useState("timestamp");
  const [sortDir, setSortDir] = useState("asc");
  const [hovered, setHovered] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [t, h] = await Promise.all([API.traces(), API.health()]);
      if (Array.isArray(t.runs)) setRuns(t.runs);
      setHealth(h);
      setLive(true);
    } catch {
      setLive(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  async function runTest(mode) {
    if (running) return;
    setRunning(mode);
    setRunMsg("");
    try {
      const { ok, data } = await API.run(mode === "single" ? { mode, prompt: promptText } : { mode });
      if (!ok || !data.ok) {
        setRunMsg(data?.error || "Run failed.");
      } else {
        const okN = data.results.filter(r => r.ok).length;
        setRunMsg(`Completed ${data.results.length} prompt(s): ${okN} ok, ${data.results.length - okN} failed.`);
        if (mode === "single") setPromptText("");
      }
    } catch {
      setRunMsg("Could not reach the server. Is server.py running?");
    } finally {
      setRunning(null);
      refresh();
    }
  }

  const sorted = useMemo(() => {
    return [...runs].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [runs, sortKey, sortDir]);

  const stats = useMemo(() => {
    // Quota-exhausted runs are an infra limit, not system behavior — exclude
    // them from success rate and latency stats.
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

  function handleSort(key) {
    if (!key) return;
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  const srColor = stats.successRate >= 80 ? C.emerald : stats.successRate >= 50 ? C.amber : C.red;
  const busy = running !== null;

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: "100vh", fontFamily: "Inter, -apple-system, system-ui, sans-serif", fontSize: 13 }}>
      {/* Nav */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", height: 50, position: "sticky", top: 0, background: C.bg, zIndex: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: C.heading, letterSpacing: "-0.2px" }}>Prompt Latency Tracer</span>
          <Badge
            color={live ? C.emerald : C.amber}
            bg={live ? C.okBg : "#1C1500"}
            border={live ? "#0C3018" : "#2A2000"}
            label={live ? "LIVE" : "SAMPLE DATA"}
            title={live ? "Connected to server.py" : "Server not reachable — showing sample data"}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <DynatraceBadge dt={health?.dynatrace} />
          <GoogleBadge g={health?.google} />
        </div>
      </div>

      <div style={{ padding: 24 }}>
        {/* Low-quota warning */}
        {health?.google?.warning && (
          <div style={{ marginBottom: 16, padding: "11px 16px", background: "#1C1500", border: "1px solid #2A2000", borderRadius: 9, fontSize: 12.5, color: C.amber, display: "flex", gap: 8 }}>
            <span>⚠️</span>
            <span>
              {health.google.remaining_total === 0
                ? "Google quota is exhausted for today across all keys. Add another GOOGLE_API_KEY in .env or wait for the daily reset."
                : `Running low on Google quota — only ${health.google.remaining_total} request(s) left today across ${health.google.keys.length} key(s). Add another key or expect 429s soon.`}
            </span>
          </div>
        )}

        {/* Run controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 14, marginBottom: 20 }}>
          <div style={{ ...styles.card, padding: "16px 18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.heading, marginBottom: 4 }}>Automatic test</div>
              <div style={{ fontSize: 11.5, color: C.muted, lineHeight: 1.5 }}>Runs the built-in benchmark prompts (the <code style={{ color: C.cyan }}>main</code> suite).</div>
            </div>
            <button onClick={() => runTest("auto")} disabled={busy}
              style={{ marginTop: 14, background: busy ? "#0E2233" : C.cyan, color: busy ? C.muted : "#001019", border: "none", borderRadius: 8, padding: "9px 0", fontSize: 12.5, fontWeight: 600, cursor: busy ? "default" : "pointer" }}>
              {running === "auto" ? <><span className="spinner" />Running…</> : "Run automatic test"}
            </button>
          </div>

          <div style={{ ...styles.card, padding: "16px 18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.heading, marginBottom: 4 }}>Self test</div>
              <div style={{ fontSize: 11.5, color: C.muted, lineHeight: 1.5, marginBottom: 10 }}>Trace your own prompt end-to-end.</div>
              <input
                value={promptText}
                onChange={e => setPromptText(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && promptText.trim() && !busy) runTest("single"); }}
                placeholder="Type a prompt and press Enter…"
                disabled={busy}
                style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, padding: "9px 12px", fontSize: 12.5, outline: "none" }}
              />
            </div>
            <button onClick={() => runTest("single")} disabled={busy || !promptText.trim()}
              style={{ marginTop: 12, alignSelf: "flex-start", background: (busy || !promptText.trim()) ? "#0E2233" : C.violet, color: (busy || !promptText.trim()) ? C.muted : "#0A0414", border: "none", borderRadius: 8, padding: "9px 20px", fontSize: 12.5, fontWeight: 600, cursor: (busy || !promptText.trim()) ? "default" : "pointer" }}>
              {running === "single" ? <><span className="spinner" />Running…</> : "Run prompt"}
            </button>
          </div>
        </div>
        {runMsg && <div style={{ marginTop: -8, marginBottom: 18, fontSize: 12, color: C.mutedMid }}>{runMsg}</div>}

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
          {[
            { label: "Runs", value: stats.total, color: C.heading, sub: stats.quotaCount ? `${stats.quotaCount} quota-skipped` : null },
            { label: "Success rate", value: `${stats.successRate}%`, color: srColor, sub: "excl. quota runs" },
            { label: "Avg latency", value: fmtMs(stats.avgMs), color: C.cyan, sub: "excl. quota runs" },
            { label: "p95 latency", value: fmtMs(stats.p95Ms), color: C.amber, sub: null },
            { label: "Total tokens", value: stats.totalTokens.toLocaleString(), color: C.violet, sub: null },
          ].map(({ label, value, color, sub }) => (
            <div key={label} style={{ ...styles.card, padding: "14px 18px" }}>
              <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 7 }}>{label}</div>
              <div style={{ fontSize: 22, fontWeight: 600, color, fontFamily: "ui-monospace, monospace", letterSpacing: "-0.5px" }}>{value}</div>
              {sub && <div style={{ fontSize: 9.5, color: C.muted, marginTop: 5 }}>{sub}</div>}
            </div>
          ))}
        </div>

        {/* Table */}
        <div style={{ ...styles.card, overflow: "hidden", marginBottom: 18 }}>
          <div style={{ padding: "11px 18px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, fontWeight: 500, color: C.mutedMid, textTransform: "uppercase", letterSpacing: "0.09em" }}>Runs · {runs.length} total</span>
            <span style={{ fontSize: 11, color: C.muted }}>Click any row to expand details</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
              <thead>
                <tr>
                  {COLS.map(({ label, key, w }) => (
                    <th key={label} onClick={() => handleSort(key)} style={{ ...styles.thCell, width: w ?? "auto" }}>
                      {label}
                      {key && sortKey === key && <span style={{ color: C.cyan, marginLeft: 4 }}>{sortDir === "asc" ? "↑" : "↓"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.length === 0 && (
                  <tr><td colSpan={7} style={{ ...styles.tdCell, textAlign: "center", color: C.muted, padding: "28px 0" }}>No runs yet — start an automatic or self test above.</td></tr>
                )}
                {sorted.map((run, i) => {
                  const isExpanded = expandedId === run.traceId;
                  const isHovered = hovered === run.traceId;
                  const rowBg = isExpanded ? "#0D1B2E" : isHovered ? "#0B1826" : "transparent";
                  return (
                    <React.Fragment key={run.traceId}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : run.traceId)}
                        onMouseEnter={() => setHovered(run.traceId)}
                        onMouseLeave={() => setHovered(null)}
                        style={{ borderBottom: isExpanded ? `1px solid transparent` : `1px solid ${C.border}`, cursor: "pointer", background: rowBg, transition: "background 0.1s" }}>
                        <td style={{ ...styles.tdCell, color: C.muted, fontFamily: "monospace", fontSize: 11 }}>{i + 1}</td>
                        <td style={{ ...styles.tdCell, fontFamily: "ui-monospace, monospace", fontSize: 11, color: C.muted, whiteSpace: "nowrap" }}>{fmtTime(run.timestamp)}</td>
                        <td style={{ ...styles.tdCell, maxWidth: 280 }}>
                          <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: C.text }}>{run.prompt}</div>
                        </td>
                        <td style={{ ...styles.tdCell, fontFamily: "ui-monospace, monospace", fontSize: 11, color: C.muted }}>{run.model}</td>
                        <td style={{ ...styles.tdCell, fontFamily: "ui-monospace, monospace", fontSize: 12, color: run.totalTokens ? C.text : C.muted }}>{run.totalTokens || "—"}</td>
                        <td style={styles.tdCell}>
                          {(() => {
                            const st = runStatus(run);
                            const cfg = {
                              ok: { bg: C.okBg, color: C.emerald, border: "#0C3018", label: "OK" },
                              quota: { bg: "#1C1500", color: C.amber, border: "#2A2000", label: "QUOTA" },
                              error: { bg: C.errBg, color: C.red, border: "#320A14", label: "ERR" },
                            }[st];
                            return (
                              <span title={run.errorMsg || ""} style={{
                                background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`,
                                borderRadius: 4, fontSize: 10, padding: "2px 7px", fontWeight: 600, letterSpacing: "0.05em"
                              }}>
                                {cfg.label}
                              </span>
                            );
                          })()}
                        </td>
                        <td style={{ ...styles.tdCell, paddingRight: 18 }}>
                          <WaterfallBar run={run} maxMs={maxMs} />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} style={{ padding: "16px 22px 18px", background: C.cardAlt, borderBottom: `1px solid ${C.border}` }}>
                            <RunDetail run={run} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Charts */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ ...styles.card, padding: "16px 20px 12px" }}>
            <div style={{ fontSize: 10, fontWeight: 500, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
            <div style={{ fontSize: 10, fontWeight: 500, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 14 }}>
              Tokens · successful runs only
            </div>
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
            ) : (
              <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontSize: 12 }}>
                No successful runs with token data yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

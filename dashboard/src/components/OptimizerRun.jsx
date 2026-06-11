import React, { useState } from "react";
import { C, fmtMs, fmtDateTime, styles } from "../theme.js";

function Delta({ value, pct, fmt = v => v, invert = false }) {
  if (value == null) return <span style={{ color: C.muted }}>—</span>;
  const improved = invert ? value < 0 : value > 0;
  const sign = value > 0 ? "−" : "+";
  return (
    <span style={{ color: improved ? C.emerald : C.amber, fontFamily: "monospace", fontSize: 12 }}>
      {sign}{fmt(Math.abs(value))}{pct != null ? ` (${Math.abs(pct)}%)` : ""}
    </span>
  );
}

function PromptColumn({ label, text, accent }) {
  const words = text ? text.trim().split(/\s+/).filter(Boolean).length : 0;
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
        {label}
        <span style={{ marginLeft: 8, color: C.mutedMid, textTransform: "none", letterSpacing: 0 }}>
          {text?.length ?? 0} chars · {words} words
        </span>
      </div>
      <div style={{
        background: C.bg, border: `1px solid ${C.border}`, borderLeft: `3px solid ${accent}`,
        borderRadius: 8, padding: "12px 14px", fontSize: 12.5, lineHeight: 1.55,
        color: C.text, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflowY: "auto",
      }}>
        {text || "—"}
      </div>
    </div>
  );
}

function MetricsRow({ metrics }) {
  if (!metrics?.baseline) return null;
  const { baseline, optimized, savings } = metrics;
  const rows = [
    { label: "Tokens", b: baseline.tokens, o: optimized?.tokens, d: savings?.tokens, pct: savings?.tokens_pct },
    { label: "Latency", b: baseline.total_ms, o: optimized?.total_ms, d: savings?.total_ms, pct: savings?.total_ms_pct, fmt: fmtMs },
    { label: "Inference", b: baseline.inference_ms, o: optimized?.inference_ms, d: savings?.inference_ms, fmt: fmtMs },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 14 }}>
      {rows.map(({ label, b, o, d, pct, fmt }) => (
        <div key={label} style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, padding: "10px 12px" }}>
          <div style={{ fontSize: 10, color: C.muted, marginBottom: 6 }}>{label}</div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "monospace", marginBottom: 4 }}>
            <span style={{ color: C.muted }}>Before</span>
            <span style={{ color: C.text }}>{fmt ? fmt(b) : b}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "monospace", marginBottom: 4 }}>
            <span style={{ color: C.muted }}>After</span>
            <span style={{ color: C.cyan }}>{o != null ? (fmt ? fmt(o) : o) : "—"}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <span style={{ color: C.muted }}>Δ</span>
            <Delta value={d} pct={pct} fmt={fmt} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function OptimizationRun({ run, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const savings = run.metrics?.savings;
  const improved = savings && savings.tokens > 0;

  return (
    <div style={{ ...styles.card, overflow: "hidden", marginBottom: 12 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", textAlign: "left", background: open ? C.cardAlt : "transparent",
          border: "none", color: C.text, padding: "12px 16px", cursor: "pointer",
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
        }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>{fmtDateTime(run.timestamp)}</div>
          <div style={{ fontSize: 12.5, color: C.heading, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {run.original_prompt}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          {savings?.tokens != null && (
            <span style={{
              fontSize: 11, fontFamily: "monospace", fontWeight: 600,
              color: improved ? C.emerald : C.amber,
            }}>
              {savings.tokens > 0 ? "−" : "+"}{Math.abs(savings.tokens)} tok
            </span>
          )}
          <span style={{ color: C.muted, fontSize: 14 }}>{open ? "▾" : "▸"}</span>
        </div>
      </button>
      {open && (
        <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${C.border}` }}>
          <div style={{ display: "flex", gap: 14, marginTop: 14 }}>
            <PromptColumn label="Original" text={run.original_prompt} accent={C.violet} />
            <PromptColumn label="Optimized" text={run.optimized_prompt} accent={C.emerald} />
          </div>
          <MetricsRow metrics={run.metrics} />
          {run.report && (
            <details style={{ marginTop: 14 }}>
              <summary style={{ fontSize: 11, color: C.mutedMid, cursor: "pointer", userSelect: "none" }}>Full agent report</summary>
              <pre style={{
                marginTop: 8, padding: "12px 14px", background: C.bg, border: `1px solid ${C.border}`,
                borderRadius: 8, fontSize: 11.5, lineHeight: 1.5, whiteSpace: "pre-wrap",
                fontFamily: "ui-monospace, monospace", color: C.text, overflow: "auto", maxHeight: 280,
              }}>{run.report}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export function OptimizeMetrics({ metrics }) {
  return <MetricsRow metrics={metrics} />;
}

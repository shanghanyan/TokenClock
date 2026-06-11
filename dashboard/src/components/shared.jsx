import React from "react";
import { C } from "../theme.js";

export function Badge({ color, bg, border, label, title }) {
  return (
    <span title={title} style={{
      display: "inline-flex", alignItems: "center", gap: 6, background: bg, color,
      border: `1px solid ${border}`, borderRadius: 6, fontSize: 11, padding: "4px 9px",
      fontWeight: 500, whiteSpace: "nowrap", cursor: "default",
    }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

export function AgentBadge({ agent }) {
  if (!agent) return null;
  const cfg = !agent.adk_available
    ? { color: C.red, bg: C.errBg, border: "#320A14", label: "Agent: not installed" }
    : { color: C.emerald, bg: C.okBg, border: "#0C3018", label: "Agent: ready" };
  const title = [
    agent.adk_available ? "Prompt optimizer (Google ADK + Gemini)" : "pip install google-adk",
    agent.model ? `Model: ${agent.model}` : null,
  ].filter(Boolean).join(" · ");
  return <Badge {...cfg} title={title} />;
}

export function GoogleBadge({ g }) {
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

export function NavTab({ href, active, children }) {
  return (
    <a href={href} style={{
      fontSize: 13, fontWeight: active ? 600 : 500, color: active ? C.heading : C.mutedMid,
      textDecoration: "none", padding: "6px 12px", borderRadius: 6,
      background: active ? "#0D1B2E" : "transparent",
      border: active ? `1px solid ${C.borderMid}` : "1px solid transparent",
    }}>
      {children}
    </a>
  );
}

export function QuotaWarning({ health }) {
  if (!health?.google?.warning) return null;
  return (
    <div style={{ marginBottom: 16, padding: "11px 16px", background: "#1C1500", border: "1px solid #2A2000", borderRadius: 9, fontSize: 12.5, color: C.amber, display: "flex", gap: 8 }}>
      <span>⚠️</span>
      <span>
        {health.google.remaining_total === 0
          ? "Google quota is exhausted for today across all keys. Add another GOOGLE_API_KEY in .env or wait for the daily reset."
          : `Running low on Google quota — only ${health.google.remaining_total} request(s) left today across ${health.google.keys.length} key(s). Add another key or expect 429s soon.`}
      </span>
    </div>
  );
}

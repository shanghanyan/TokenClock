export const C = {
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

export const STATUS_COLOR = { ok: C.cyan, quota: C.amber, error: C.red };

export const fmtMs = v => {
  if (v >= 1000) return `${(v / 1000).toFixed(2)}s`;
  return `${Math.round(v)}ms`;
};

export const fmtTime = v => new Date(v).toLocaleTimeString("en-US", {
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});

export const fmtDateTime = v => new Date(v).toLocaleString("en-US", {
  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});

export function percentile(arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const idx = (p / 100) * (s.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return s[lo] + (idx - lo) * ((s[hi] ?? s[lo]) - s[lo]);
}

export const styles = {
  detailLabel: { fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 },
  thCell: { padding: "8px 14px", textAlign: "left", color: C.muted, fontWeight: 400, fontSize: 10, letterSpacing: "0.09em", textTransform: "uppercase", cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", borderBottom: `1px solid ${C.border}` },
  tdCell: { padding: "10px 14px" },
  card: { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10 },
};

export const PROMPT_STORAGE_KEY = "tokenclock_optimize_prompt";

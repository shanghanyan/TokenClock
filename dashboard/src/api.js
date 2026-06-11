export const API = {
  traces: () => fetch("/api/traces").then(r => r.json()),
  health: () => fetch("/api/health").then(r => r.json()),
  clearTraces: () => fetch("/api/traces/clear", { method: "POST" }).then(async r => ({ ok: r.ok, data: await r.json() })),
  optimizations: () => fetch("/api/optimizations").then(r => r.json()),
  clearOptimizations: () => fetch("/api/optimizations/clear", { method: "POST" }).then(async r => ({ ok: r.ok, data: await r.json() })),
  run: (body) => fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).then(async r => ({ ok: r.ok, data: await r.json() })),
  optimize: (body) => fetch("/api/optimize", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).then(async r => ({ ok: r.ok, data: await r.json() })),
};

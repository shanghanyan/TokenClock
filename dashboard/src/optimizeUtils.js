/** Client-side fallbacks for optimized prompt text (legacy records included). */

export function parseOptimizedFromReport(report) {
  if (!report) return null;
  const m = report.match(/#{1,3}\s*Optimized prompt\b[^\n]*(?:\s*\n+|\s+)([\s\S]*?)(?=\n#{1,3}\s+\S|$)/i);
  if (!m) return null;
  let body = m[1].trim().replace(/^\*\*|\*\*$/g, "");
  const fenced = body.match(/^```(?:\w*\n)?([\s\S]+?)```\s*$/);
  if (fenced) body = fenced[1].trim();
  const lines = [];
  for (const line of body.split("\n")) {
    if (/^#{1,3}\s/.test(line)) break;
    if (/^[-*]\s/.test(line) && lines.length) break;
    lines.push(line);
  }
  body = lines.join("\n").trim();
  return body || null;
}

export function resolveOptimizedPrompt(run) {
  if (run.optimized_prompt) return run.optimized_prompt;
  const fromMeasure = run.metrics?.optimized?.prompt;
  if (fromMeasure?.trim()) return fromMeasure.trim();
  return parseOptimizedFromReport(run.report);
}

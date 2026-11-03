export interface Requirement {
  id: string;
  description: string;
  priority: "P0" | "P1";
  acceptance: string;
  verification: string;
}

/** Deterministic mirror of backend/app/spec/engine.py (local preview only). */
export function parseSpecification(spec: string): Requirement[] {
  const sentences = spec
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim().replace(/[.]+$/, ""))
    .filter(Boolean);
  return sentences.map((s, i) => {
    const high = /auth|log ?in|secur|password|payment|deploy/i.test(s);
    return {
      id: `REQ-${String(i + 1).padStart(3, "0")}`,
      description: s,
      priority: high ? "P0" : "P1",
      acceptance: `Demonstrated by execution/test: ${s.slice(0, 80)}`,
      verification: "execution+test",
    };
  });
}

export function routeModel(taskKind: string): { model: string; reason: string } {
  const complex = /architect|debug|multi-file|plan|schema|threat/i.test(taskKind);
  return complex
    ? { model: "muse-wonder-1.0", reason: "complex reasoning task" }
    : { model: "muse-spark-1.3", reason: "routine engineering task" };
}

// Design tokens — Cotejar (del handoff de UI). Fuente de verdad: design_handoff_cotejar/README.md
export const C = {
  bg: "#EAEEEE", surface: "#FFFFFF", border: "#DDE3E4", border2: "#E2E8E8",
  ink: "#16242A", ink2: "#3A474C", muted: "#5C6B71", faint: "#7C8A8F",
  teal: "#0E6E78", tealDeep: "#0A363C", teal50: "#E6F0F1", tealWash: "#F2FAFA",
  green: "#1F8A5B", greenInk: "#145C3C", greenBg: "#E6F4EC",
  red: "#C0413B", redInk: "#8E2B27", redBg: "#FBEAE9", redBorder: "#E3B7B4",
  amber: "#C2860E", amberInk: "#855A06", amberBg: "#FBF1DC", amberBorder: "#EBDDB6",
  neutralBg: "#EEF1F2",
};

// Veredicto backend -> presentación
export const VERDICTS = {
  valido: { label: "VÁLIDO", kind: "ok", glyph: "✓" },
  revision_manual: { label: "REVISIÓN MANUAL", kind: "amber", glyph: "!" },
  invalido: { label: "INVÁLIDO", kind: "red", glyph: "✕" },
  faltan_datos: { label: "FALTAN DATOS", kind: "info", glyph: "i" },
} as const;

export const MATURITY = {
  calibrado: { label: "Calibrado", cls: "mat-ok" },
  calibrando: { label: "Calibrando", cls: "mat-amber" },
  solo_reglas: { label: "Solo reglas", cls: "mat-neutral" },
} as const;

export function maturityLabel(m?: string | null): string {
  return (MATURITY as Record<string, { label: string }>)[m || "solo_reglas"]?.label || m || "—";
}

// errores de fetch -> texto legible (centraliza el patrón repetido en las pantallas)
export function errMsg(e: unknown): string {
  return String((e as Error)?.message || e);
}

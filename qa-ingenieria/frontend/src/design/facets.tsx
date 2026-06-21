// Tokens y componentes de FACETAS compartidos (Templates + Observatorio) — colores/etiquetas por eje,
// barra de progreso y chips de faceta etiquetados. Misma paleta del handoff de Templates.
import type { FacetRegistry } from "../api/client";

export const FACET_AXIS: Record<string, { label: string; color: string }> = {
  tipo:         { label: "Tipo",         color: "#0e7c86" },
  organizacion: { label: "Empresa",      color: "#4f46e5" },
  disciplina:   { label: "Disciplina",   color: "#475569" },
  jurisdiccion: { label: "Jurisdicción", color: "#b45309" },
  proyecto:     { label: "Proyecto",     color: "#9333ea" },
};
export const FACET_ORDER = ["tipo", "organizacion", "disciplina", "jurisdiccion", "proyecto"];

export const pctColor = (pct: number) => (pct >= 80 ? "#12a87f" : pct >= 50 ? "#e0a32e" : "#d0473e");

export function Bar({ pct, color, h = 6 }: { pct: number; color: string; h?: number }) {
  return (
    <div style={{ position: "relative", height: h, background: "#edf1f3", borderRadius: h / 2, overflow: "hidden", flex: 1, minWidth: 44 }}>
      <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: color, borderRadius: h / 2, transition: "width .3s" }} />
    </div>
  );
}

// Chips de faceta etiquetados (Empresa: Camuzzi · Proyecto: CAREM25 …) desde el dict crudo
// {organizacion:'camuzzi', disciplina:'instrumentacion', ...} traduciendo a etiquetas vía el registro.
export function FacetChips({ facetas, registry, size = 11 }: {
  facetas: Record<string, string>; registry: FacetRegistry | null; size?: number;
}) {
  const ents = FACET_ORDER
    .filter((k) => facetas?.[k])
    .map((k) => ({ k, meta: FACET_AXIS[k] || { label: k, color: "#94a3b8" }, value: registry?.valores?.[k]?.[facetas[k]] || facetas[k] }));
  if (!ents.length) return <span style={{ fontSize: size, color: "#aab4bb", fontStyle: "italic" }}>sin facetas</span>;
  return <>{ents.map(({ k, meta, value }) => (
    <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 5, background: "#f6f8f9", border: "1px solid #e6ecef", borderRadius: 6, padding: "2px 7px 2px 6px" }}>
      <span style={{ width: 6, height: 6, borderRadius: 2, background: meta.color, flex: "none" }} />
      <span style={{ fontSize: size - 0.5, color: "#8a99a3" }}>{meta.label}:</span>
      <span style={{ fontSize: size, color: "#3f5260", fontWeight: 500 }}>{value}</span>
    </span>
  ))}</>;
}

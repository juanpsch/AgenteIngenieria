import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type ReglaStat, type FacetRegistry } from "../api/client";
import { ChevronDown, Search, X } from "lucide-react";
import { FACET_AXIS, FACET_ORDER, Bar, FacetChips, pctColor } from "../design/facets";
import "./Templates.css";

// Observatorio de reglas: planilla de todas las reglas con su estadística de cumplimiento, facetada,
// para analizar qué regla afecta a qué familias/docs y revisar el feedback humano. (Look del handoff Templates.)
const SEV: Record<string, { fg: string; bg: string; border: string }> = {
  bloqueante: { fg: "#b42318", bg: "#fef3f2", border: "#fecdc9" },
  mayor:      { fg: "#946312", bg: "#fdf4e3", border: "#f0ddb6" },
  menor:      { fg: "#5b6b78", bg: "#eef1f4", border: "#dce3e8" },
  observacion:{ fg: "#0d6b53", bg: "#e4f4ee", border: "#c3e7da" },
};
const FB: { k: string; glyph: string; label: string; fg: string; bg: string; border: string }[] = [
  { k: "de_acuerdo", glyph: "👍", label: "de acuerdo", fg: "#0d6b53", bg: "#e9f5f0", border: "#c3e7da" },
  { k: "no_aplica",  glyph: "🚫", label: "no aplica",  fg: "#5b6b78", bg: "#f4f6f8", border: "#dce3e8" },
  { k: "regla_mal",  glyph: "⚠",  label: "regla mal",  fg: "#946312", bg: "#fdf6ea", border: "#f0ddb6" },
];

const PctCell = ({ pct }: { pct: number | null }) => {
  if (pct == null) return <span style={{ fontSize: 12, color: "#b6c0c7" }}>—</span>;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
      <Bar pct={pct} color={pctColor(pct)} />
      <span style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 11.5, fontWeight: 600, color: "#2b3a45", width: 38, textAlign: "right" }}>{pct}%</span>
    </div>
  );
};
const FeedbackChips = ({ fb, size = 10 }: { fb: Record<string, number>; size?: number }) => {
  const items = FB.filter((f) => fb?.[f.k]);
  if (!items.length) return <span style={{ fontSize: 11, color: "#aab4bb" }}>—</span>;
  return <>{items.map((f) => (
    <span key={f.k} title={f.label} style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: size, fontWeight: 600, color: f.fg, background: f.bg, border: `1px solid ${f.border}`, borderRadius: 20, padding: "1px 7px" }}>{f.glyph} {fb[f.k]}</span>
  ))}</>;
};
const Stat = ({ value, label, color }: { value: React.ReactNode; label: string; color?: string }) => (
  <div style={{ flex: 1, background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, padding: "13px 16px", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
    <div style={{ fontSize: 24, fontWeight: 700, color: color || "#13252f", lineHeight: 1 }}>{value}</div>
    <div style={{ fontSize: 11.5, color: "#7e8f9a", marginTop: 5 }}>{label}</div>
  </div>
);

export function Reglas() {
  const [data, setData] = useState<ReglaStat[]>([]);
  const [reg, setReg] = useState<FacetRegistry | null>(null);
  const [norma, setNorma] = useState("");
  const [filtro, setFiltro] = useState<{ eje: string; valor: string }>({ eje: "", valor: "" });
  const [q, setQ] = useState("");
  const [soloDatos, setSoloDatos] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.reglasEstadisticas().then(setData).catch(() => {});
    api.facetasRegistry().then(setReg).catch(() => {});
  }, []);

  const normaLabel = useMemo(() => {
    const m: Record<string, string> = {};
    for (const r of data) if (r.norma_id) m[r.norma_id] = r.norma_ref || r.norma_id;
    return m;
  }, [data]);
  const normas = useMemo(() => [...new Set(data.map((r) => r.norma_id).filter(Boolean))].sort() as string[], [data]);
  const ejesConValor = FACET_ORDER.filter((e) => data.some((r) => r.familias.some((f) => f.facetas?.[e])));
  const valoresDe = (eje: string) => [...new Set(data.flatMap((r) => r.familias.map((f) => f.facetas?.[eje])).filter(Boolean))].sort() as string[];

  const filtradas = useMemo(() => data.filter((r) => {
    if (soloDatos && !r.n) return false;
    if (norma && r.norma_id !== norma) return false;
    if (filtro.eje && filtro.valor && !r.familias.some((f) => f.facetas?.[filtro.eje] === filtro.valor)) return false;
    if (q && !`${r.descripcion || ""} ${r.req_id}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }).sort((a, b) => (b.feedback.regla_mal || 0) - (a.feedback.regla_mal || 0) || b.n - a.n), [data, norma, filtro, q, soloDatos]);

  // Resumen sobre el set filtrado
  const conPct = filtradas.filter((r) => r.pct_cumple != null);
  const avgPct = conPct.length ? Math.round(conPct.reduce((s, r) => s + (r.pct_cumple || 0), 0) / conPct.length) : null;
  const conReglaMal = filtradas.filter((r) => (r.feedback.regla_mal || 0) + (r.feedback_amplio?.regla_mal || 0) > 0).length;

  const COLS = "26px 2.5fr 1.1fr 0.9fr 60px 1.5fr 1.2fr";
  const selStyle: React.CSSProperties = { fontSize: 12.5, padding: "6px 9px", border: "1px solid #dce3e8", borderRadius: 8, background: "#fafbfc", color: "#2b3a45" };
  return (
    <div className="ct-fade">
      {/* Resumen */}
      <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
        <Stat value={filtradas.length} label="reglas en vista" />
        <Stat value={avgPct == null ? "—" : `${avgPct}%`} label="cumplimiento promedio" color={avgPct == null ? undefined : pctColor(avgPct)} />
        <Stat value={conReglaMal} label="con juicio «regla mal»" color={conReglaMal ? "#946312" : undefined} />
      </div>

      {/* Toolbar de filtros */}
      <div style={{ background: "#fff", border: "1px solid #e7edf0", borderRadius: 12, padding: "12px 16px", marginBottom: 16, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <select value={norma} onChange={(e) => setNorma(e.target.value)} style={selStyle}>
          <option value="">Todas las normas</option>
          {normas.map((n) => <option key={n} value={n}>{normaLabel[n] || n}</option>)}
        </select>
        <span style={{ fontSize: 11.5, color: "#9aa7b0", fontWeight: 600, letterSpacing: .3 }}>FACETA</span>
        <select value={filtro.eje} onChange={(e) => setFiltro({ eje: e.target.value, valor: "" })} style={selStyle}>
          <option value="">(eje)</option>
          {ejesConValor.map((e) => <option key={e} value={e}>{FACET_AXIS[e]?.label || e}</option>)}
        </select>
        {filtro.eje && (
          <select value={filtro.valor} onChange={(e) => setFiltro({ ...filtro, valor: e.target.value })} style={selStyle}>
            <option value="">(todos)</option>
            {valoresDe(filtro.eje).map((v) => <option key={v} value={v}>{reg?.valores?.[filtro.eje]?.[v] || v}</option>)}
          </select>
        )}
        {filtro.eje && filtro.valor && (
          <button onClick={() => setFiltro({ eje: "", valor: "" })} title="Limpiar faceta" style={{ border: "none", background: "#eef1f3", width: 24, height: 24, borderRadius: "50%", cursor: "pointer", color: "#5d7180", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={13} /></button>
        )}
        <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
          <Search size={14} color="#9aa7b0" style={{ position: "absolute", left: 9 }} />
          <input placeholder="Buscar regla o id…" value={q} onChange={(e) => setQ(e.target.value)} style={{ border: "1px solid #dce3e8", borderRadius: 8, padding: "7px 10px 7px 30px", fontSize: 12.5, width: 200, background: "#fafbfc", color: "#2b3a45" }} />
        </div>
        <label style={{ fontSize: 12, color: "#5d7180", display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={soloDatos} onChange={(e) => setSoloDatos(e.target.checked)} /> solo con datos
        </label>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: "#7e8f9a" }}><b style={{ color: "#2b3a45" }}>{filtradas.length}</b> de {data.length} reglas</span>
      </div>

      {/* Tabla */}
      <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
        <div style={{ display: "grid", gridTemplateColumns: COLS, padding: "11px 18px", background: "#f7f9fa", borderBottom: "1px solid #e7edf0", fontSize: 10.5, letterSpacing: .6, fontWeight: 700, color: "#90a0aa" }}>
          <div /><div>REGLA</div><div>NORMA</div><div>SEVERIDAD</div><div style={{ textAlign: "center" }}>DOCS</div><div>CUMPLIMIENTO</div><div>FEEDBACK</div>
        </div>
        {filtradas.map((r) => {
          const sv = r.severidad ? SEV[r.severidad] || SEV.menor : null;
          const isOpen = open === r.req_id;
          return (
            <Fragment key={r.req_id}>
              <div className="tpl-leafrow" role="button" tabIndex={0} style={{ display: "grid", gridTemplateColumns: COLS, alignItems: "center", padding: "11px 18px", borderBottom: "1px solid #eef2f4", cursor: "pointer", animation: "czfade .2s ease" }}
                onClick={() => setOpen(isOpen ? null : r.req_id)} onKeyDown={(e) => { if (e.key === "Enter") setOpen(isOpen ? null : r.req_id); }}>
                <span style={{ display: "inline-flex", transition: "transform .18s", transform: isOpen ? "rotate(0deg)" : "rotate(-90deg)", color: "#7e8f9a" }}><ChevronDown size={14} /></span>
                <div style={{ paddingRight: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#1c2c36", lineHeight: 1.25 }}>{r.descripcion || r.id}</div>
                  <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 10.5, color: "#8597a2", marginTop: 2 }}>{r.req_id}</div>
                </div>
                <span style={{ fontSize: 12, color: "#52646f", paddingRight: 10 }}>{r.norma_ref || r.norma_id || "—"}</span>
                <span>{sv && <span style={{ fontSize: 10.5, fontWeight: 600, color: sv.fg, background: sv.bg, border: `1px solid ${sv.border}`, borderRadius: 6, padding: "2px 8px" }}>{r.severidad}</span>}</span>
                <span style={{ textAlign: "center", fontFamily: "ui-monospace,Menlo,monospace", fontSize: 13, fontWeight: 700, color: r.n ? "#2b3a45" : "#b6c0c7" }}>{r.n || "—"}</span>
                <span style={{ paddingRight: 12 }}><PctCell pct={r.pct_cumple} /></span>
                <span style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
                  <FeedbackChips fb={r.feedback} />
                  {FB.some((f) => r.feedback_amplio?.[f.k]) && (
                    <span title="Hay juicios a nivel norma/global: se reusan en todas las familias que usan la regla" style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 9.5, fontWeight: 600, color: "#0b6b74", background: "#eef7f8", border: "1px solid #bfe0e4", borderRadius: 20, padding: "1px 7px" }}>↗ norma</span>
                  )}
                </span>
              </div>
              {isOpen && (
                <div style={{ background: "#fbfcfc", borderBottom: "1px solid #eef2f4", padding: "10px 18px 12px", paddingLeft: 44 }}>
                  {r.familias.length ? (
                    <>
                      <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: .5, color: "#90a0aa", marginBottom: 8 }}>POR FAMILIA</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                        {r.familias.map((f) => (
                          <div key={f.tipo_doc} style={{ display: "grid", gridTemplateColumns: "1.6fr 2fr 52px 1.4fr 1.1fr", gap: 10, alignItems: "center" }}>
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontSize: 12.5, fontWeight: 600, color: "#1c2c36", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.nombre}</div>
                              <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 10, color: "#8597a2" }}>{f.tipo_doc}</div>
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}><FacetChips facetas={f.facetas || {}} registry={reg} size={10.5} /></div>
                            <span style={{ textAlign: "center", fontFamily: "ui-monospace,Menlo,monospace", fontSize: 12, color: f.n ? "#2b3a45" : "#b6c0c7" }}>{f.n || "—"}</span>
                            <span><PctCell pct={f.pct_cumple} /></span>
                            <span style={{ display: "flex", gap: 4, flexWrap: "wrap" }}><FeedbackChips fb={f.feedback} size={9.5} /></span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : <span style={{ fontSize: 12, color: "#94a3ab" }}>Sin evaluaciones registradas todavía.</span>}
                </div>
              )}
            </Fragment>
          );
        })}
        {!filtradas.length && (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "#8b9aa4" }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#5d7180" }}>Sin reglas</div>
            <div style={{ fontSize: 12.5, marginTop: 5 }}>Ninguna regla coincide con los filtros activos.</div>
          </div>
        )}
      </div>
    </div>
  );
}

import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type ReglaStat, type FacetRegistry } from "../api/client";
import { ChevronDown, Search, X, ListFilter } from "lucide-react";
import { FACET_AXIS, FACET_ORDER, Bar, FacetChips, pctColor, Stat } from "../design/facets";
import "./Templates.css";

// Observatorio de reglas: planilla facetada con su estadística de cumplimiento + feedback humano. Mismo
// lenguaje visual y pivot que Templates, pero con ejes propios de REGLAS (Norma · Severidad · Disciplina).
type RAxis = "norma" | "severidad" | "disciplina";
const RAXES: Record<RAxis, { label: string; color: string }> = {
  norma:      { label: "Norma",      color: "#0e7c86" },
  severidad:  { label: "Severidad",  color: "#b45309" },
  disciplina: { label: "Disciplina", color: "#475569" },
};
const RAXIS_ORDER: RAxis[] = ["norma", "severidad", "disciplina"];
const SEV_RANK: Record<string, number> = { bloqueante: 0, mayor: 1, menor: 2, observacion: 3 };
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

type RRow =
  | { kind: "group"; gKey: string; depth: number; axis: RAxis; value: string; empty: boolean; count: number }
  | { kind: "leaf"; rowKey: string; depth: number; r: ReglaStat };

const PctCell = ({ pct }: { pct: number | null }) => {
  if (pct == null) return <span title="Sin datos verificables todavía" style={{ fontSize: 12, color: "#b6c0c7" }}>—</span>;
  return (
    <div title="% de cumplimiento = ok / (ok + fallo), sobre lo verificable" style={{ display: "flex", alignItems: "center", gap: 7, cursor: "help" }}>
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

export function Reglas() {
  const [data, setData] = useState<ReglaStat[]>([]);
  const [reg, setReg] = useState<FacetRegistry | null>(null);
  const [order, setOrder] = useState<RAxis[]>(["norma"]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [filtro, setFiltro] = useState<{ eje: string; valor: string }>({ eje: "", valor: "" });
  const [q, setQ] = useState("");
  const [soloDatos, setSoloDatos] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.reglasEstadisticas().then(setData).catch(() => {});
    api.facetasRegistry().then(setReg).catch(() => {});
  }, []);

  const ejesConValor = FACET_ORDER.filter((e) => data.some((r) => r.familias.some((f) => f.facetas?.[e])));
  const valoresDe = (eje: string) => [...new Set(data.flatMap((r) => r.familias.map((f) => f.facetas?.[eje])).filter(Boolean))].sort() as string[];

  const filtradas = useMemo(() => data.filter((r) => {
    if (soloDatos && !r.n) return false;
    if (filtro.eje && filtro.valor && !r.familias.some((f) => f.facetas?.[filtro.eje] === filtro.valor)) return false;
    if (q && !`${r.descripcion || ""} ${r.req_id}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }).sort((a, b) => (b.feedback.regla_mal || 0) - (a.feedback.regla_mal || 0) || b.n - a.n), [data, filtro, q, soloDatos]);

  // valores de cada eje del pivot para una regla (disciplina = multivaluado)
  const rv = (r: ReglaStat, k: RAxis): string[] => {
    if (k === "disciplina") return r.disciplinas?.length ? r.disciplinas.map((d) => reg?.valores?.disciplina?.[d] || d) : ["—"];
    if (k === "norma") return [r.norma_ref || r.norma_id || "—"];
    return [r.severidad || "—"];
  };
  const sortVals = (axis: RAxis, a: string, b: string) => (a === "—" ? 1 : b === "—" ? -1 : axis === "severidad" ? (SEV_RANK[a] ?? 9) - (SEV_RANK[b] ?? 9) : a.localeCompare(b));

  const { rows, allKeys } = useMemo(() => {
    const rows: RRow[] = [];
    const keys: string[] = [];
    const rec = (items: ReglaStat[], depth: number, pathKey: string) => {
      if (depth >= order.length) { for (const r of items) rows.push({ kind: "leaf", rowKey: `${pathKey}|${r.req_id}`, depth, r }); return; }
      const ak = order[depth];
      const groups = new Map<string, ReglaStat[]>();
      for (const r of items) for (const v of rv(r, ak)) { if (!groups.has(v)) groups.set(v, []); groups.get(v)!.push(r); }
      for (const [val, list] of [...groups.entries()].sort((a, b) => sortVals(ak, a[0], b[0]))) {
        const gKey = `${pathKey}>${ak}:${val}`;
        keys.push(gKey);
        rows.push({ kind: "group", gKey, depth, axis: ak, value: val, empty: val === "—", count: list.length });
        if (!collapsed.has(gKey)) rec(list, depth + 1, gKey);
      }
    };
    rec(filtradas, 0, "");
    return { rows, allKeys: keys };
  }, [filtradas, order, collapsed, reg]);   // eslint-disable-line react-hooks/exhaustive-deps

  const moveAxis = (i: number, dir: number) => { setOrder((o) => { const j = i + dir; if (j < 0 || j >= o.length) return o; const n = [...o]; [n[i], n[j]] = [n[j], n[i]]; return n; }); setCollapsed(new Set()); };
  const removeAxis = (k: RAxis) => { setOrder((o) => o.filter((x) => x !== k)); setCollapsed(new Set()); };
  const addAxis = (k: RAxis) => { setOrder((o) => (o.includes(k) ? o : [...o, k])); setCollapsed(new Set()); };
  const toggleGroup = (g: string) => setCollapsed((c) => { const n = new Set(c); n.has(g) ? n.delete(g) : n.add(g); return n; });

  const conPct = filtradas.filter((r) => r.pct_cumple != null);
  const avgPct = conPct.length ? Math.round(conPct.reduce((s, r) => s + (r.pct_cumple || 0), 0) / conPct.length) : null;
  const conReglaMal = filtradas.filter((r) => (r.feedback.regla_mal || 0) + (r.feedback_amplio?.regla_mal || 0) > 0).length;

  const COLS = "2.6fr 1.1fr 0.9fr 60px 1.5fr 1.2fr";
  const selStyle: React.CSSProperties = { fontSize: 12.5, padding: "6px 9px", border: "1px solid #dce3e8", borderRadius: 8, background: "#fafbfc", color: "#2b3a45" };
  const CHIP_BTN: React.CSSProperties = { border: "none", background: "#f0f3f5", width: 20, height: 22, borderRadius: 5, cursor: "pointer", color: "#5b6e7b", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 };

  return (
    <div className="ct-fade">
      {/* Resumen */}
      <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
        <Stat value={filtradas.length} label="reglas en vista" title="Reglas que cumplen los filtros actuales" />
        <Stat value={avgPct == null ? "—" : `${avgPct}%`} label="cumplimiento promedio" color={avgPct == null ? undefined : pctColor(avgPct)} title="Promedio del % de cumplimiento (ok sobre lo verificable) de las reglas con datos" />
        <Stat value={conReglaMal} label="con juicio «regla mal»" color={conReglaMal ? "#946312" : undefined} title="Reglas marcadas por un humano como erradas (falso positivo/negativo)" />
      </div>

      {/* Toolbar: pivot + filtros */}
      <div style={{ background: "#fff", border: "1px solid #e7edf0", borderRadius: 12, padding: "14px 16px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 11 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div title="Tabla dinámica: agrupá las reglas por Norma / Severidad / Disciplina en el orden que elijas. Reordená con ‹ ›, sumá con + Eje, quitá con ✕." style={{ display: "flex", alignItems: "center", gap: 7, cursor: "help" }}>
            <ListFilter size={15} color="#0e7c86" />
            <span style={{ fontSize: 12.5, fontWeight: 700, color: "#34495a" }}>Agrupar en orden</span>
          </div>
          {order.map((k, i) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 4, background: "#fff", border: `1.5px solid ${RAXES[k].color}`, borderRadius: 8, padding: "3px 3px 3px 9px", boxShadow: "0 1px 2px rgba(0,0,0,.04)" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: RAXES[k].color }} />
              <span style={{ fontSize: 9.5, fontWeight: 800, color: "#9aa7b0" }}>{i + 1}</span>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: "#2b3a45" }}>{RAXES[k].label}</span>
              <button className="tpl-chipbtn" onClick={() => moveAxis(i, -1)} title="Mover antes" style={{ ...CHIP_BTN, marginLeft: 3 }}>‹</button>
              <button className="tpl-chipbtn" onClick={() => moveAxis(i, 1)} title="Mover después" style={CHIP_BTN}>›</button>
              <button className="tpl-xbtn" onClick={() => removeAxis(k)} title="Quitar eje" style={{ border: "none", background: "transparent", width: 22, height: 22, borderRadius: 5, cursor: "pointer", color: "#9aa7b0", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={12} /></button>
            </div>
          ))}
          {RAXIS_ORDER.filter((k) => !order.includes(k)).map((k) => (
            <button key={k} className="tpl-addaxis" onClick={() => addAxis(k)} style={{ border: "1.5px dashed #c7d2da", background: "#fff", borderRadius: 8, padding: "5px 11px", cursor: "pointer", fontSize: 12.5, fontWeight: 600, color: "#5d7180", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontWeight: 800 }}>+</span>{RAXES[k].label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <button className="tpl-link" onClick={() => setCollapsed(new Set(allKeys))} style={{ border: "none", background: "transparent", color: "#5d7180", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "5px 8px", borderRadius: 6 }}>colapsar todo</button>
          <button className="tpl-link" onClick={() => setCollapsed(new Set())} style={{ border: "none", background: "transparent", color: "#5d7180", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "5px 8px", borderRadius: 6 }}>expandir todo</button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11.5, color: "#9aa7b0", fontWeight: 600, letterSpacing: .3 }}>FILTRAR FACETA</span>
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
      </div>

      {/* Tabla */}
      <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
        <div style={{ display: "grid", gridTemplateColumns: COLS, padding: "11px 18px", background: "#f7f9fa", borderBottom: "1px solid #e7edf0", fontSize: 10.5, letterSpacing: .6, fontWeight: 700, color: "#90a0aa" }}>
          <div>REGLA</div><div>NORMA</div><div>SEVERIDAD</div><div style={{ textAlign: "center" }}>DOCS</div><div>CUMPLIMIENTO</div><div>FEEDBACK</div>
        </div>
        {rows.map((row) => {
          if (row.kind === "group") {
            const ax = RAXES[row.axis];
            const col = collapsed.has(row.gKey);
            return (
              <div key={row.gKey} className="tpl-grouprow" role="button" tabIndex={0} onClick={() => toggleGroup(row.gKey)} onKeyDown={(e) => { if (e.key === "Enter") toggleGroup(row.gKey); }}
                style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 18px", paddingLeft: 18 + row.depth * 20, background: row.depth === 0 ? "#f4f7f8" : "#fafbfc", borderBottom: "1px solid #eef2f4", cursor: "pointer" }}>
                <span style={{ display: "inline-flex", transition: "transform .18s", transform: col ? "rotate(-90deg)" : "rotate(0deg)", color: "#7e8f9a" }}><ChevronDown size={13} /></span>
                <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: .5, color: ax.color, textTransform: "uppercase" }}>{ax.label}</span>
                <span style={{ fontSize: 13.5, fontWeight: 700, color: row.empty ? "#aab4bb" : "#1c2c36", fontStyle: row.empty ? "italic" : "normal" }}>{row.empty ? "sin valor" : row.value}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#8b9aa4", background: "#eef2f4", borderRadius: 10, padding: "1px 8px" }}>{row.count}</span>
              </div>
            );
          }
          const r = row.r;
          const sv = r.severidad ? SEV[r.severidad] || SEV.menor : null;
          const isOpen = open === r.req_id;
          return (
            <Fragment key={row.rowKey}>
              <div className="tpl-leafrow" role="button" tabIndex={0} style={{ display: "grid", gridTemplateColumns: COLS, alignItems: "center", padding: "11px 18px", borderBottom: "1px solid #eef2f4", cursor: "pointer", animation: "czfade .2s ease" }}
                onClick={() => setOpen(isOpen ? null : r.req_id)} onKeyDown={(e) => { if (e.key === "Enter") setOpen(isOpen ? null : r.req_id); }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 6 + order.length * 18, paddingRight: 12, minWidth: 0 }}>
                  <span style={{ display: "inline-flex", transition: "transform .18s", transform: isOpen ? "rotate(0deg)" : "rotate(-90deg)", color: "#7e8f9a", flex: "none" }}><ChevronDown size={13} /></span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#1c2c36", lineHeight: 1.25 }}>{r.descripcion || r.id}</div>
                    <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 10.5, color: "#8597a2", marginTop: 2 }}>{r.req_id}</div>
                  </div>
                </div>
                <span style={{ fontSize: 12, color: "#52646f", paddingRight: 10 }}>{r.norma_ref || r.norma_id || "—"}</span>
                <span>{sv && <span title={`Severidad si la regla falla: ${r.severidad}`} style={{ fontSize: 10.5, fontWeight: 600, color: sv.fg, background: sv.bg, border: `1px solid ${sv.border}`, borderRadius: 6, padding: "2px 8px" }}>{r.severidad}</span>}</span>
                <span title="Documentos en los que se evaluó la regla" style={{ textAlign: "center", fontFamily: "ui-monospace,Menlo,monospace", fontSize: 13, fontWeight: 700, color: r.n ? "#2b3a45" : "#b6c0c7" }}>{r.n || "—"}</span>
                <span style={{ paddingRight: 12 }}><PctCell pct={r.pct_cumple} /></span>
                <span style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
                  <FeedbackChips fb={r.feedback} />
                  {FB.some((f) => r.feedback_amplio?.[f.k]) && (
                    <span title="Hay juicios a nivel norma/global: se reusan en todas las familias que usan la regla" style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 9.5, fontWeight: 600, color: "#0b6b74", background: "#eef7f8", border: "1px solid #bfe0e4", borderRadius: 20, padding: "1px 7px" }}>↗ norma</span>
                  )}
                </span>
              </div>
              {isOpen && (
                <div style={{ background: "#fbfcfc", borderBottom: "1px solid #eef2f4", padding: "10px 18px 12px", paddingLeft: 44 + order.length * 18 }}>
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

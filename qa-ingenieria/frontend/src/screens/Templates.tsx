import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { api, type Tipo, type Cobertura, type FacetRegistry } from "../api/client";
import { MaturityBadge, Dropzone } from "../components/ui";
import { PreviewModal } from "../components/PreviewModal";
import { ZonaEditor } from "../components/ZonaEditor";
import { RequisitosEditor } from "../components/RequisitosEditor";
import { useActivity } from "../components/Activity";
import { errMsg } from "../design/tokens";
import { Plus, Trash2, ArrowLeft, Eye, Upload, ChevronDown, Pencil, Search, X, Copy, ListFilter } from "lucide-react";
import "./Templates.css";

// ───────────────── Vista facetada (handoff design_handoff_templates_referencia) ─────────────────
type AxisKey = "tipo" | "empresa" | "disc" | "juris" | "proyecto";
const AXES: Record<AxisKey, { label: string; color: string; facet: string }> = {
  tipo:     { label: "Tipo",         color: "#0e7c86", facet: "tipo" },
  empresa:  { label: "Empresa",      color: "#4f46e5", facet: "organizacion" },
  disc:     { label: "Disciplina",   color: "#475569", facet: "disciplina" },
  juris:    { label: "Jurisdicción", color: "#b45309", facet: "jurisdiccion" },
  proyecto: { label: "Proyecto",     color: "#9333ea", facet: "proyecto" },
};
const AXIS_ORDER: AxisKey[] = ["tipo", "empresa", "disc", "juris", "proyecto"];
const T = 5;   // umbral "calibrado"

type Maturity = "solo_reglas" | "calibrando" | "calibrado";
interface Family {
  id: string; name: string;
  tipo: string | null; empresa: string | null; disc: string[]; juris: string | null; proyecto: string | null;
  disciplinas: string[]; examples: number; inheritsFrom?: string; maturity: Maturity;
}

// Mapea cada familia (API) a la forma facetada del diseño, traduciendo ids de faceta a etiquetas del registro.
function buildFamilies(tipos: Tipo[], reg: FacetRegistry | null): Family[] {
  const lbl = (eje: string, v?: string | null) => (v ? reg?.valores?.[eje]?.[v] || v : null);
  return tipos.map((t) => {
    const f = t.facetas || {};
    return {
      id: t.tipo_doc, name: t.nombre,
      tipo: lbl("tipo", f.tipo), empresa: lbl("organizacion", f.organizacion),
      disc: f.disciplina ? [lbl("disciplina", f.disciplina)!] : [],
      juris: f.jurisdiccion || null, proyecto: lbl("proyecto", f.proyecto),
      disciplinas: (t.disciplinas || []).map((d) => reg?.valores?.disciplina?.[d] || d),
      examples: t.refs_count, inheritsFrom: t.hereda_de || undefined,
      maturity: (t.maturity as Maturity) || "solo_reglas",
    };
  });
}

interface MatMeta { key: Maturity; label: string; fg: string; bg: string; border: string; dot: string; pct: number; sub: string; }
function matMeta(f: Family): MatMeta {
  const ex = f.examples;
  const pct = Math.min(100, Math.round((ex / T) * 100));
  if (f.maturity === "calibrado") return { key: "calibrado", label: "Calibrado", fg: "#0d6b53", bg: "#e4f4ee", border: "#c3e7da", dot: "#12a87f", pct, sub: `${ex} ejemplos · decisivo` };
  if (f.maturity === "calibrando") return { key: "calibrando", label: "Calibrando", fg: "#946312", bg: "#fdf4e3", border: "#f0ddb6", dot: "#e0a32e", pct, sub: `${ex}/${T} · faltan ${T - ex} para decidir` };
  const sub = f.inheritsFrom ? `sin ejemplos · hereda de ${f.inheritsFrom}` : `${ex}/${T} · sumá ${Math.max(2 - ex, 1)} para calibrar`;
  return { key: "solo_reglas", label: "Solo reglas", fg: "#5b6b78", bg: "#eef1f4", border: "#dce3e8", dot: "#94a3b8", pct, sub };
}

const valuesFor = (f: Family, k: AxisKey): string[] =>
  k === "disc" ? (f.disc.length ? f.disc : ["—"]) : [(f[k] as string | null) || "—"];
const coordChips = (f: Family) => (["tipo", "empresa", "juris", "proyecto"] as AxisKey[])
  .map((k) => ({ axisKey: k, color: AXES[k].color, value: f[k] as string | null }))
  .filter((c): c is { axisKey: AxisKey; color: string; value: string } => !!c.value);

type Row =
  | { kind: "group"; gKey: string; depth: number; axisKey: AxisKey; value: string; empty: boolean; count: number }
  | { kind: "leaf"; rowKey: string; depth: number; f: Family };

function buildRows(families: Family[], order: AxisKey[], collapsed: Set<string>): Row[] {
  const rows: Row[] = [];
  const rec = (items: Family[], depth: number, pathKey: string) => {
    if (depth >= order.length) {
      for (const f of items) rows.push({ kind: "leaf", rowKey: `${pathKey}|${f.id}`, depth, f });
      return;
    }
    const ak = order[depth];
    const groups = new Map<string, Family[]>();
    for (const f of items) for (const v of valuesFor(f, ak)) { if (!groups.has(v)) groups.set(v, []); groups.get(v)!.push(f); }
    const entries = [...groups.entries()].sort((a, b) => (a[0] === "—" ? 1 : b[0] === "—" ? -1 : a[0].localeCompare(b[0])));
    for (const [val, list] of entries) {
      const gKey = `${pathKey}>${ak}:${val}`;
      rows.push({ kind: "group", gKey, depth, axisKey: ak, value: val, empty: val === "—", count: list.length });
      if (!collapsed.has(gKey)) rec(list, depth + 1, gKey);
    }
  };
  rec(families, 0, "");
  return rows;
}
function allGroupKeys(families: Family[], order: AxisKey[]): string[] {
  const keys: string[] = [];
  const rec = (items: Family[], depth: number, pathKey: string) => {
    if (depth >= order.length) return;
    const ak = order[depth];
    const groups = new Map<string, Family[]>();
    for (const f of items) for (const v of valuesFor(f, ak)) { if (!groups.has(v)) groups.set(v, []); groups.get(v)!.push(f); }
    for (const [val, list] of groups) { const g = `${pathKey}>${ak}:${val}`; keys.push(g); rec(list, depth + 1, g); }
  };
  rec(families, 0, "");
  return keys;
}

const MAT_DEFS: { k: Maturity; label: string; fg: string; bg: string; border: string; dot: string }[] = [
  { k: "solo_reglas", label: "Solo reglas", fg: "#5b6b78", bg: "#f4f6f8", border: "#dce3e8", dot: "#94a3b8" },
  { k: "calibrando", label: "Calibrando", fg: "#946312", bg: "#fdf6ea", border: "#f0ddb6", dot: "#e0a32e" },
  { k: "calibrado", label: "Calibrado", fg: "#0d6b53", bg: "#e9f5f0", border: "#c3e7da", dot: "#12a87f" },
];
const S_LABEL: CSSProperties = { fontSize: 11, fontWeight: 700, letterSpacing: .5, color: "#90a0aa" };
const CHIP_BTN: CSSProperties = { border: "none", background: "#f0f3f5", width: 20, height: 22, borderRadius: 5, cursor: "pointer", color: "#5b6e7b", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 };
const LINK_BTN: CSSProperties = { border: "none", background: "transparent", color: "#5d7180", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "5px 8px", borderRadius: 6 };

const MatPill = ({ m, size = 11 }: { m: MatMeta; size?: number }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 5, background: m.bg, border: `1px solid ${m.border}`, borderRadius: 6, padding: "2px 8px" }}>
    <span style={{ width: 7, height: 7, borderRadius: "50%", background: m.dot, flex: "none" }} />
    <span style={{ fontSize: size, fontWeight: 600, color: m.fg }}>{m.label}</span>
  </span>
);
const Progress = ({ m, h = 5 }: { m: MatMeta; h?: number }) => (
  <div style={{ position: "relative", height: h, background: "#edf1f3", borderRadius: h / 2, overflow: "hidden" }}>
    <div style={{ position: "absolute", inset: 0, width: `${m.pct}%`, background: m.dot, borderRadius: h / 2, transition: "width .3s" }} />
  </div>
);
const GroupRow = ({ r, collapsed, onToggle, indent, compact }: {
  r: Extract<Row, { kind: "group" }>; collapsed: boolean; onToggle: () => void; indent: number; compact?: boolean;
}) => {
  const ax = AXES[r.axisKey];
  return (
    <div className="tpl-grouprow" role="button" tabIndex={0} onClick={onToggle} onKeyDown={(e) => { if (e.key === "Enter") onToggle(); }}
      style={{ display: "flex", alignItems: "center", gap: compact ? 8 : 9, padding: compact ? "8px 14px" : "9px 18px", paddingLeft: indent, background: r.depth === 0 ? "#f4f7f8" : "#fafbfc", borderBottom: "1px solid #eef2f4", cursor: "pointer" }}>
      <span style={{ display: "inline-flex", transition: "transform .18s", transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)", color: "#7e8f9a" }}><ChevronDown size={compact ? 12 : 13} /></span>
      <span style={{ fontSize: compact ? 9.5 : 10, fontWeight: 800, letterSpacing: .5, color: ax.color, textTransform: "uppercase" }}>{ax.label}</span>
      <span style={{ fontSize: compact ? 12.5 : 13.5, fontWeight: 700, color: r.empty ? "#aab4bb" : "#1c2c36", fontStyle: r.empty ? "italic" : "normal" }}>{r.empty ? "sin valor" : r.value}</span>
      <span style={{ fontSize: compact ? 10.5 : 11, fontWeight: 700, color: "#8b9aa4", background: "#eef2f4", borderRadius: 10, padding: "1px 8px" }}>{r.count}</span>
    </div>
  );
};

export function Templates() {
  const [tipos, setTipos] = useState<Tipo[]>([]);
  const [reg, setReg] = useState<FacetRegistry | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [showNew, setShowNew] = useState(false);

  const [view, setView] = useState<"A" | "B" | "C">("A");
  const [order, setOrder] = useState<AxisKey[]>(["tipo", "disc"]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [maturity, setMaturity] = useState<Set<Maturity>>(new Set());
  const [search, setSearch] = useState("");
  const [facet, setFacet] = useState<{ axisKey: AxisKey; value: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = () => api.listTipos().then(setTipos).catch(() => {});
  useEffect(() => { load(); api.facetasRegistry().then(setReg).catch(() => {}); }, []);

  async function open(id: string) { setDetail(await api.getTipo(id)); }
  async function del(id: string) { await api.delTipo(id); load(); }

  const families = useMemo(() => buildFamilies(tipos, reg), [tipos, reg]);
  useEffect(() => { if (view === "B" && !selected && families.length) setSelected(families[0].id); }, [view, selected, families]);

  const baseList = (applyMat: boolean) => {
    const s = search.trim().toLowerCase();
    return families.filter((f) => {
      if (s && !(f.name.toLowerCase().includes(s) || f.id.toLowerCase().includes(s))) return false;
      if (facet && !valuesFor(f, facet.axisKey).includes(facet.value)) return false;
      if (applyMat && maturity.size && !maturity.has(f.maturity)) return false;
      return true;
    });
  };
  const filtered = useMemo(() => baseList(true), [families, search, facet, maturity]);   // eslint-disable-line react-hooks/exhaustive-deps
  const matBase = useMemo(() => baseList(false), [families, search, facet]);             // eslint-disable-line react-hooks/exhaustive-deps
  const rows = useMemo(() => buildRows(filtered, order, collapsed), [filtered, order, collapsed]);

  const moveAxis = (i: number, dir: number) => { setOrder((o) => { const j = i + dir; if (j < 0 || j >= o.length) return o; const n = [...o]; [n[i], n[j]] = [n[j], n[i]]; return n; }); setCollapsed(new Set()); };
  const removeAxis = (k: AxisKey) => { setOrder((o) => o.filter((x) => x !== k)); setCollapsed(new Set()); };
  const addAxis = (k: AxisKey) => { setOrder((o) => (o.includes(k) ? o : [...o, k])); setCollapsed(new Set()); };
  const toggleGroup = (g: string) => setCollapsed((c) => { const n = new Set(c); n.has(g) ? n.delete(g) : n.add(g); return n; });
  const setFacetVal = (axisKey: AxisKey, value: string | null) => { if (value && value !== "—") setFacet({ axisKey, value }); };
  const toggleMaturity = (m: Maturity) => setMaturity((s) => { const n = new Set(s); n.has(m) ? n.delete(m) : n.add(m); return n; });
  const clearFilters = () => { setSearch(""); setFacet(null); setMaturity(new Set()); };

  if (detail) return <Detalle d={detail} onBack={() => { setDetail(null); load(); }} reload={() => open(detail.tipo_doc)} />;

  const calibMark = Math.min(100, Math.round((2 / T) * 100));

  // ── Vista A: tabla pivot ──
  const GRID_A = "2.3fr 1.5fr 1.2fr 74px 1.15fr 58px";
  const renderA = () => (
    <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
      <div style={{ display: "grid", gridTemplateColumns: GRID_A, padding: "11px 18px", background: "#f7f9fa", borderBottom: "1px solid #e7edf0", fontSize: 10.5, letterSpacing: .6, fontWeight: 700, color: "#90a0aa" }}>
        <div>TIPO DE DOCUMENTO</div><div>FACETAS</div><div>DISCIPLINAS</div><div style={{ textAlign: "center" }}>REF.</div><div>MADUREZ</div><div />
      </div>
      {rows.map((r) => r.kind === "group"
        ? <GroupRow key={r.gKey} r={r} collapsed={collapsed.has(r.gKey)} onToggle={() => toggleGroup(r.gKey)} indent={18 + r.depth * 20} />
        : (() => {
          const m = matMeta(r.f);
          return (
            <div key={r.rowKey} className="tpl-leafrow" style={{ display: "grid", gridTemplateColumns: GRID_A, alignItems: "center", padding: "12px 18px", borderBottom: "1px solid #eef2f4", animation: "czfade .2s ease" }}>
              <div style={{ paddingLeft: 4 + order.length * 20, paddingRight: 14 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "#1c2c36", lineHeight: 1.25 }}>{r.f.name}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
                  <span style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 11, color: "#8597a2" }}>{r.f.id}</span>
                  {r.f.inheritsFrom && <span style={{ fontSize: 10.5, color: "#a07a2e", background: "#fdf6e7", border: "1px solid #f0e2bf", borderRadius: 5, padding: "0 6px" }}>↳ hereda {r.f.inheritsFrom}</span>}
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, paddingRight: 12 }}>
                {coordChips(r.f).map((c) => (
                  <button key={c.axisKey} className="tpl-coord" onClick={() => setFacetVal(c.axisKey, c.value)} title={`Filtrar por ${AXES[c.axisKey].label}`} style={{ display: "flex", alignItems: "center", gap: 5, background: "#f6f8f9", border: "1px solid #e6ecef", borderRadius: 6, padding: "2px 7px 2px 6px", cursor: "pointer" }}>
                    <span style={{ width: 6, height: 6, borderRadius: 2, background: c.color }} />
                    <span style={{ fontSize: 11.5, color: "#3f5260", fontWeight: 500 }}>{c.value}</span>
                  </button>
                ))}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, paddingRight: 12 }}>
                {r.f.disciplinas.map((d) => <span key={d} style={{ fontSize: 11, color: "#52646f", background: "#eef2f4", borderRadius: 5, padding: "2px 7px" }}>{d}</span>)}
              </div>
              <div style={{ textAlign: "center" }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: r.f.examples > 0 ? "#2b3a45" : "#b6c0c7" }}>{r.f.examples}</span>
                <div style={{ fontSize: 9.5, color: "#a3b0b8", letterSpacing: .3 }}>docs</div>
              </div>
              <div style={{ paddingRight: 10 }}>
                <MatPill m={m} />
                <div style={{ marginTop: 6 }}><Progress m={m} /></div>
                <div style={{ fontSize: 10, color: "#94a3ab", marginTop: 3 }}>{m.sub}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                <button className="tpl-iconbtn" title="Editar" onClick={() => open(r.f.id)} style={{ border: "none", background: "#f0f3f5", width: 28, height: 28, borderRadius: 7, cursor: "pointer", color: "#5d7180", display: "flex", alignItems: "center", justifyContent: "center" }}><Pencil size={14} /></button>
                <button className="tpl-iconbtn-del" title="Borrar" onClick={() => del(r.f.id)} style={{ border: "none", background: "#f0f3f5", width: 28, height: 28, borderRadius: 7, cursor: "pointer", color: "#9aa7b0", display: "flex", alignItems: "center", justifyContent: "center" }}><Trash2 size={14} /></button>
              </div>
            </div>
          );
        })())}
    </div>
  );

  // ── Vista B: pivot compacto + panel ──
  const sel = view === "B" ? families.find((f) => f.id === selected) || null : null;
  const renderB = () => {
    const m = sel ? matMeta(sel) : null;
    return (
      <div style={{ display: "grid", gridTemplateColumns: "minmax(380px,1fr) 1.15fr", gap: 18, alignItems: "start" }}>
        <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
          {rows.map((r) => r.kind === "group"
            ? <GroupRow key={r.gKey} r={r} collapsed={collapsed.has(r.gKey)} onToggle={() => toggleGroup(r.gKey)} indent={18 + r.depth * 20} compact />
            : (
              <div key={r.rowKey} className="tpl-leafrow-b" onClick={() => setSelected(r.f.id)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", paddingLeft: 4 + order.length * 20, borderBottom: "1px solid #eef2f4", cursor: "pointer", background: selected === r.f.id ? "#eef7f8" : "#fff", borderLeft: `3px solid ${selected === r.f.id ? "#0e7c86" : "transparent"}` }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: matMeta(r.f).dot, flex: "none" }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#1c2c36", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.f.name}</div>
                  <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 10.5, color: "#8597a2" }}>{r.f.id}</div>
                </div>
                <span style={{ fontSize: 11, color: "#8b9aa4", flex: "none" }}>{r.f.examples} ref</span>
              </div>
            ))}
        </div>
        {sel && m ? (
          <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, boxShadow: "0 1px 3px rgba(20,40,55,.05)", position: "sticky", top: 0, animation: "czpanel .22s ease", overflow: "hidden" }}>
            <div style={{ padding: "18px 20px", borderBottom: "1px solid #eef2f4", background: "linear-gradient(180deg,#f8fafb,#fff)" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#13252f", lineHeight: 1.25 }}>{sel.name}</h2>
                  <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 12, color: "#7e8f9a", marginTop: 4 }}>{sel.id}</div>
                </div>
                <MatPill m={m} size={12} />
              </div>
              {sel.inheritsFrom && <div style={{ marginTop: 10, fontSize: 12, color: "#a07a2e", background: "#fdf6e7", border: "1px solid #f0e2bf", borderRadius: 7, padding: "7px 10px" }}>↳ Hereda ejemplos de <b>{sel.inheritsFrom}</b> mientras no tenga propios.</div>}
            </div>
            <div style={{ padding: "18px 20px" }}>
              <div style={S_LABEL}>CALIBRACIÓN</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8 }}>
                <span style={{ fontSize: 30, fontWeight: 700, color: "#1c2c36" }}>{sel.examples}</span>
                <span style={{ fontSize: 13, color: "#7e8f9a" }}>ejemplos · objetivo {T}</span>
              </div>
              <div style={{ position: "relative", height: 9, background: "#edf1f3", borderRadius: 5, marginTop: 10, overflow: "hidden" }}>
                <div style={{ position: "absolute", inset: 0, width: `${m.pct}%`, background: m.dot, borderRadius: 5, transition: "width .3s" }} />
                <div style={{ position: "absolute", top: -2, bottom: -2, left: `${calibMark}%`, width: 2, background: "#c2cdd4" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "#94a3ab" }}>
                <span>{m.sub}</span><span>calibrando ≥2 · decisivo ≥{T}</span>
              </div>

              <div style={{ ...S_LABEL, marginTop: 22 }}>COORDENADAS (FACETAS)</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 1, marginTop: 8, border: "1px solid #eef2f4", borderRadius: 9, overflow: "hidden" }}>
                {(["tipo", "empresa", "disc", "juris", "proyecto"] as AxisKey[]).map((k) => {
                  const has = k === "disc" ? sel.disc.length > 0 : !!sel[k];
                  const display = k === "disc" ? (sel.disc.length ? sel.disc.join(", ") : "sin valor") : ((sel[k] as string | null) || "sin valor");
                  return (
                    <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", background: has ? "#fff" : "#fbfcfc" }}>
                      <span style={{ width: 7, height: 7, borderRadius: 2, background: has ? AXES[k].color : "#cfd6db", flex: "none" }} />
                      <span style={{ fontSize: 11.5, fontWeight: 600, color: "#6b7d89", width: 92, flex: "none" }}>{AXES[k].label}</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: has ? "#2b3a45" : "#aab4bb", fontStyle: has ? "normal" : "italic" }}>{display}</span>
                    </div>
                  );
                })}
              </div>

              <div style={{ ...S_LABEL, marginTop: 22 }}>DISCIPLINAS</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                {sel.disciplinas.map((d) => <span key={d} style={{ fontSize: 12, color: "#3f5260", background: "#eef2f4", borderRadius: 6, padding: "3px 10px" }}>{d}</span>)}
              </div>

              <div style={{ display: "flex", gap: 9, marginTop: 24 }}>
                <button className="tpl-primary" onClick={() => open(sel.id)} style={{ flex: 1, border: "none", background: "#0e7c86", color: "#fff", fontSize: 13, fontWeight: 600, padding: 10, borderRadius: 9, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
                  <Pencil size={14} /> Editar reglas y ejemplos
                </button>
                <button className="tpl-secondary" title="Duplicar (próximamente)" style={{ border: "1px solid #e1e8ec", background: "#fff", color: "#5d7180", fontSize: 13, fontWeight: 600, padding: "10px 14px", borderRadius: 9, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}><Copy size={14} /> Duplicar</button>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, padding: 40, textAlign: "center", color: "#8b9aa4", fontSize: 13 }}>Elegí una familia de la lista.</div>
        )}
      </div>
    );
  };

  // ── Vista C: tarjetas agrupadas por el primer eje ──
  const renderC = () => {
    const ak = order[0];
    let sections: { axisKey: AxisKey | null; value: string; empty: boolean; count: number; families: Family[] }[];
    if (!ak) {
      sections = [{ axisKey: null, value: "", empty: false, count: filtered.length, families: filtered }];
    } else {
      const groups = new Map<string, Family[]>();
      for (const f of filtered) for (const v of valuesFor(f, ak)) { if (!groups.has(v)) groups.set(v, []); groups.get(v)!.push(f); }
      const entries = [...groups.entries()].sort((a, b) => (a[0] === "—" ? 1 : b[0] === "—" ? -1 : a[0].localeCompare(b[0])));
      sections = entries.map(([val, list]) => ({ axisKey: ak, value: val, empty: val === "—", count: list.length, families: list }));
    }
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
        {sections.map((s, si) => {
          const ax = s.axisKey ? AXES[s.axisKey] : { label: "Todas", color: "#0e7c86" };
          return (
            <div key={si}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <span style={{ width: 9, height: 9, borderRadius: 3, background: ax.color }} />
                <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: .6, color: ax.color, textTransform: "uppercase" }}>{ax.label}</span>
                {s.axisKey && <span style={{ fontSize: 15, fontWeight: 700, color: s.empty ? "#aab4bb" : "#1c2c36", fontStyle: s.empty ? "italic" : "normal" }}>{s.empty ? "sin valor" : s.value}</span>}
                <span style={{ fontSize: 11, fontWeight: 700, color: "#8b9aa4", background: "#e7edf0", borderRadius: 10, padding: "1px 9px" }}>{s.count}</span>
                <div style={{ flex: 1, height: 1, background: "#e1e8ec" }} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(310px,1fr))", gap: 14 }}>
                {s.families.map((f) => {
                  const m = matMeta(f);
                  const needsCalib = f.examples < T && m.key !== "calibrado";
                  return (
                    <div key={f.id} className="tpl-card" style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, padding: "15px 16px", boxShadow: "0 1px 3px rgba(20,40,55,.05)", animation: "czfade .2s ease", display: "flex", flexDirection: "column", gap: 11 }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 14, fontWeight: 700, color: "#13252f", lineHeight: 1.25 }}>{f.name}</div>
                          <div style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 11, color: "#8597a2", marginTop: 3 }}>{f.id}</div>
                        </div>
                        <MatPill m={m} size={10.5} />
                      </div>
                      <div>
                        <Progress m={m} h={6} />
                        <div style={{ fontSize: 10.5, color: "#94a3ab", marginTop: 5 }}>{m.sub}</div>
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                        {coordChips(f).map((c) => (
                          <span key={c.axisKey} style={{ display: "flex", alignItems: "center", gap: 5, background: "#f6f8f9", border: "1px solid #e6ecef", borderRadius: 6, padding: "2px 7px 2px 6px" }}>
                            <span style={{ width: 6, height: 6, borderRadius: 2, background: c.color }} />
                            <span style={{ fontSize: 11, color: "#3f5260" }}>{c.value}</span>
                          </span>
                        ))}
                        {f.disciplinas.map((d) => <span key={d} style={{ fontSize: 11, color: "#52646f", background: "#eef2f4", borderRadius: 6, padding: "2px 7px" }}>{d}</span>)}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid #eef2f4", paddingTop: 11 }}>
                        <span style={{ fontSize: 11.5, color: "#7e8f9a" }}><b style={{ color: "#2b3a45", fontSize: 13 }}>{f.examples}</b> referencias</span>
                        {needsCalib
                          ? <button className="tpl-calib" onClick={() => open(f.id)} style={{ border: "1px dashed #c7d2da", background: "#fff", borderRadius: 7, padding: "5px 10px", cursor: "pointer", fontSize: 11.5, fontWeight: 600, color: "#0e7c86", display: "flex", alignItems: "center", gap: 5 }}><Plus size={13} /> Calibrar</button>
                          : <button className="tpl-secondary" onClick={() => open(f.id)} style={{ border: "1px solid #e1e8ec", background: "#fff", borderRadius: 7, padding: "5px 10px", cursor: "pointer", fontSize: 11.5, fontWeight: 600, color: "#5d7180" }}>Ver reglas</button>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="ct-fade">
      {/* selector de vista + nuevo template */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
        <div style={{ display: "flex", background: "#eef1f3", borderRadius: 9, padding: 3, gap: 2 }}>
          {([["A", "Tabla pivot"], ["B", "Pivot + panel"], ["C", "Tarjetas"]] as const).map(([k, l]) => {
            const on = view === k;
            return (
              <button key={k} className="tpl-tab" onClick={() => setView(k)} style={{ border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600, padding: "7px 12px", borderRadius: 7, display: "flex", alignItems: "center", gap: 6, background: on ? "#fff" : "transparent", color: on ? "#0e7c86" : "#6b7d89", boxShadow: on ? "0 1px 3px rgba(20,40,55,.12)" : "none" }}>
                <span style={{ fontSize: 10, fontWeight: 800, opacity: .6 }}>{k}</span>{l}
              </button>
            );
          })}
        </div>
        <button className="tpl-primary" onClick={() => setShowNew(true)} style={{ marginLeft: "auto", border: "none", cursor: "pointer", background: "#0e7c86", color: "#fff", fontSize: 13, fontWeight: 600, padding: "9px 15px", borderRadius: 9, display: "flex", alignItems: "center", gap: 7, boxShadow: "0 2px 8px rgba(14,124,134,.3)" }}>
          <Plus size={15} /> Nuevo template
        </button>
      </div>

      {/* toolbar: pivot + filtros */}
      <div style={{ background: "#fff", border: "1px solid #e7edf0", borderRadius: 12, padding: "14px 16px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 11 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <ListFilter size={15} color="#0e7c86" />
            <span style={{ fontSize: 12.5, fontWeight: 700, color: "#34495a" }}>Pivot — agrupar en orden</span>
          </div>
          {order.map((k, i) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 4, background: "#fff", border: `1.5px solid ${AXES[k].color}`, borderRadius: 8, padding: "3px 3px 3px 9px", boxShadow: "0 1px 2px rgba(0,0,0,.04)" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: AXES[k].color }} />
              <span style={{ fontSize: 9.5, fontWeight: 800, color: "#9aa7b0" }}>{i + 1}</span>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: "#2b3a45" }}>{AXES[k].label}</span>
              <button className="tpl-chipbtn" onClick={() => moveAxis(i, -1)} title="Mover antes" style={{ ...CHIP_BTN, marginLeft: 3 }}>‹</button>
              <button className="tpl-chipbtn" onClick={() => moveAxis(i, 1)} title="Mover después" style={CHIP_BTN}>›</button>
              <button className="tpl-xbtn" onClick={() => removeAxis(k)} title="Quitar eje" style={{ border: "none", background: "transparent", width: 22, height: 22, borderRadius: 5, cursor: "pointer", color: "#9aa7b0", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={12} /></button>
            </div>
          ))}
          {AXIS_ORDER.filter((k) => !order.includes(k)).map((k) => (
            <button key={k} className="tpl-addaxis" onClick={() => addAxis(k)} style={{ border: "1.5px dashed #c7d2da", background: "#fff", borderRadius: 8, padding: "5px 11px", cursor: "pointer", fontSize: 12.5, fontWeight: 600, color: "#5d7180", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontWeight: 800 }}>+</span>{AXES[k].label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <button className="tpl-link" onClick={() => setCollapsed(new Set(allGroupKeys(filtered, order)))} style={LINK_BTN}>colapsar todo</button>
          <button className="tpl-link" onClick={() => setCollapsed(new Set())} style={LINK_BTN}>expandir todo</button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
            <Search size={14} color="#9aa7b0" style={{ position: "absolute", left: 9 }} />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar familia o id…" style={{ border: "1px solid #dce3e8", borderRadius: 8, padding: "7px 10px 7px 30px", fontSize: 12.5, width: 220, background: "#fafbfc", color: "#2b3a45" }} />
          </div>
          <span style={{ fontSize: 11.5, color: "#9aa7b0", fontWeight: 600, letterSpacing: .3 }}>MADUREZ</span>
          {MAT_DEFS.map((md) => {
            const count = matBase.filter((f) => f.maturity === md.k).length;
            const op = maturity.size === 0 || maturity.has(md.k) ? 1 : .4;
            return (
              <button key={md.k} onClick={() => toggleMaturity(md.k)} style={{ border: `1.5px solid ${md.border}`, background: md.bg, borderRadius: 20, padding: "4px 11px 4px 8px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, opacity: op, transition: "opacity .15s" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: md.dot }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: md.fg }}>{md.label}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: md.fg, background: "rgba(255,255,255,.65)", borderRadius: 9, padding: "0 6px" }}>{count}</span>
              </button>
            );
          })}
          {facet && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#eef7f8", border: "1px solid #bfe0e4", borderRadius: 20, padding: "4px 6px 4px 11px" }}>
              <span style={{ fontSize: 11.5, color: "#0b6b74", fontWeight: 600 }}>{AXES[facet.axisKey].label}: {facet.value}</span>
              <button onClick={() => setFacet(null)} style={{ border: "none", background: "#d6ecee", width: 18, height: 18, borderRadius: "50%", cursor: "pointer", color: "#0b6b74", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={11} /></button>
            </div>
          )}
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: "#7e8f9a" }}><b style={{ color: "#2b3a45" }}>{filtered.length}</b> de {families.length} familias</span>
        </div>
      </div>

      {/* contenido */}
      {filtered.length === 0
        ? (
          <div style={{ textAlign: "center", padding: "80px 20px", color: "#8b9aa4" }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: "#5d7180" }}>Sin resultados</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>Ninguna familia coincide con los filtros activos.</div>
            <button onClick={clearFilters} style={{ marginTop: 14, border: "1px solid #cdd6dc", background: "#fff", borderRadius: 8, padding: "7px 14px", cursor: "pointer", fontSize: 12.5, fontWeight: 600, color: "#0e7c86" }}>Limpiar filtros</button>
          </div>
        )
        : view === "A" ? renderA() : view === "B" ? renderB() : renderC()}

      {showNew && <NuevoTemplate onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />}
    </div>
  );
}

function Detalle({ d, onBack, reload }: { d: any; onBack: () => void; reload: () => void }) {
  const [yaml, setYaml] = useState<string>(d.yaml || "");
  const [msg, setMsg] = useState("");
  const [refFile, setRefFile] = useState<File | null>(null);
  const [refMsg, setRefMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [prev, setPrev] = useState<{ src: string; title: string; tag: string } | null>(null);
  const { run } = useActivity();

  async function guardar() {
    try { await api.putTipo(d.tipo_doc, yaml); setMsg("Guardado ✓"); reload(); }
    catch (e) { setMsg("Error: " + errMsg(e)); }
  }
  async function addRef() {
    if (!refFile) return;
    setBusy(true); setRefMsg("");
    try {
      await run(`Agregar referencia: ${refFile.name}`, () => api.addRef(d.tipo_doc, refFile),
        ["Subiendo archivo…", "Renderizando páginas…", "Calculando embeddings (calibrando)…"]);
      setRefFile(null); setRefMsg("Referencia agregada ✓"); reload();
    } catch (e) { setRefMsg("No se pudo subir: " + errMsg(e)); }
    finally { setBusy(false); }
  }
  async function delRef(rid: string) {
    setRefMsg("");
    try { await api.delRef(d.tipo_doc, rid); reload(); }
    catch (e) { setRefMsg("No se pudo borrar: " + errMsg(e)); }
  }
  async function delNeg(rid: string) {
    setRefMsg("");
    try { await api.delNeg(d.tipo_doc, rid); reload(); }
    catch (e) { setRefMsg("No se pudo borrar: " + errMsg(e)); }
  }

  return (
    <div className="ct-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <button className="btn btn-ghost" style={{ alignSelf: "flex-start" }} onClick={onBack}><ArrowLeft size={15} /> Volver</button>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><h3 style={{ margin: 0 }}>{d.nombre}</h3><div className="faint mono">{d.tipo_doc}</div></div>
          <div style={{ textAlign: "right" }}><MaturityBadge m={d.maturity} /><div className="mono" style={{ fontSize: 22, color: "var(--teal)" }}>{d.refs_count}<span className="faint" style={{ fontSize: 12 }}> / 5 ejemplos</span></div></div>
        </div>
      </div>

      <div className="card">
        <div className="dim-h">Documentos de referencia</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12 }}>
          {(d.referencias || []).map((r: any) => {
            const url = api.refPreviewUrl(d.tipo_doc, r.ref_id);
            const promovido = r.origin === "promovido";
            const tag = promovido ? "Promovido" : "Inicial";
            return (
              <div key={r.ref_id} style={{ border: "1px solid var(--border2)", borderRadius: 10, overflow: "hidden" }}>
                <div style={{ position: "relative", height: 112, background: "#F4F7F7", cursor: "zoom-in", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", fontSize: 11, color: "var(--faint)" }}
                  onClick={() => setPrev({ src: url, title: r.filename, tag })}>
                  sin vista previa
                  <img src={url} alt={r.filename} style={{ width: "100%", height: "100%", objectFit: "cover", position: "absolute" }}
                    onError={(e) => { e.currentTarget.style.display = "none"; }} />
                </div>
                <div style={{ padding: 8 }}>
                  <div className="mono" style={{ fontSize: 10.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={r.filename}>{r.filename}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                    <span className="chip" style={{ background: promovido ? "var(--teal50)" : "var(--neutral-bg)", color: promovido ? "var(--teal)" : "var(--muted)" }}>{tag}</span>
                    <span>
                      <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Previsualizar" onClick={() => setPrev({ src: url, title: r.filename, tag })}><Eye size={13} /></button>
                      <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Borrar" onClick={() => delRef(r.ref_id)}><Trash2 size={13} color="var(--red)" /></button>
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
          {!(d.referencias || []).length && <div className="faint">Sin referencias todavía.</div>}
        </div>
        <div style={{ marginTop: 14 }}>
          <Dropzone file={refFile} onFile={(f) => { setRefFile(f); setRefMsg(""); }} size={22}
            title="Agregar un documento de referencia"
            subtitle="PDF o imagen — cada ejemplo calibra el template" />
          <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center" }}>
            <button className="btn btn-primary" disabled={!refFile || busy} onClick={addRef}>
              {busy ? "Subiendo y calibrando…" : "Subir referencia"}
            </button>
            {refMsg && <span className={refMsg.startsWith("No se pudo") ? "" : "muted"} style={refMsg.startsWith("No se pudo") ? { color: "var(--red-ink)" } : undefined}>{refMsg}</span>}
          </div>
        </div>
      </div>

      {!!(d.negativos || []).length && (
        <div className="card">
          <div className="dim-h">Contra-ejemplos (negativos) · {d.negativos_count ?? (d.negativos || []).length}</div>
          <div className="faint" style={{ fontSize: 11.5, margin: "2px 0 8px" }}>
            Documentos rechazados que el modelo daba admisibles: el score <b>penaliza</b> a los parecidos. No se promueven; se agregan a pedido desde el caso.
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12 }}>
            {(d.negativos || []).map((r: any) => {
              const url = api.negPreviewUrl(d.tipo_doc, r.ref_id);
              return (
                <div key={r.ref_id} style={{ border: "1px solid var(--red-border, #e3b7b7)", borderRadius: 10, overflow: "hidden" }}>
                  <div style={{ position: "relative", height: 112, background: "#FAF4F4", cursor: "zoom-in", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", fontSize: 11, color: "var(--faint)" }}
                    onClick={() => setPrev({ src: url, title: r.filename, tag: "Contra-ejemplo" })}>
                    sin vista previa
                    <img src={url} alt={r.filename} style={{ width: "100%", height: "100%", objectFit: "cover", position: "absolute" }}
                      onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  </div>
                  <div style={{ padding: 8 }}>
                    <div className="mono" style={{ fontSize: 10.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={r.filename}>{r.filename}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                      <span className="chip mat-red">contra-ejemplo</span>
                      <span>
                        <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Previsualizar" onClick={() => setPrev({ src: url, title: r.filename, tag: "Contra-ejemplo" })}><Eye size={13} /></button>
                        <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Borrar" onClick={() => delNeg(r.ref_id)}><Trash2 size={13} color="var(--red)" /></button>
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ZonaEditor
        tipoDoc={d.tipo_doc}
        referencias={d.referencias || []}
        zonasIniciales={d.zonas || []}
        onSaved={() => reload()}
      />

      <RequisitosEditor
        tipoDoc={d.tipo_doc}
        disciplinas={d.disciplinas || []}
        resueltosIniciales={d.requisitos_resueltos || []}
        onSaved={() => reload()}
      />

      <div className="card">
        <div className="dim-h">Template (YAML)</div>
        <textarea className="input mono" style={{ minHeight: 320, fontSize: 12 }} value={yaml} onChange={(e) => setYaml(e.target.value)} />
        <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center" }}>
          <button className="btn btn-primary" onClick={guardar}>Guardar cambios</button>
          {msg && <span className="muted">{msg}</span>}
        </div>
      </div>

      {prev && <PreviewModal src={prev.src} title={prev.title} tag={prev.tag} onClose={() => setPrev(null)} />}
    </div>
  );
}

function NuevoTemplate({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [tid, setTid] = useState(""); const [nombre, setNombre] = useState("");
  const [modo, setModo] = useState<"ejemplo" | "especificacion">("ejemplo");
  const [yaml, setYaml] = useState(""); const [cob, setCob] = useState<Cobertura[]>([]);
  const [usarRefs, setUsarRefs] = useState(true);
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState("");
  const { run } = useActivity();

  async function analizar() {
    if (!files.length) return;
    setBusy(true); setMsg("");
    try {
      const label = files.length === 1 ? `Analizar ${files[0].name}` : `Analizar ${files.length} ejemplos`;
      const r = await run(label, () => api.capturarMulti(files, tid, nombre, modo),
        ["Leyendo los documentos…", "Detectando zona de identidad…", "Consolidando reglas entre ejemplos…"]);
      setYaml(r.yaml); setCob(r.cobertura || []);
      if (r.template?.tipo_doc) setTid(r.template.tipo_doc);
    } catch (e) { setMsg("Error: " + errMsg(e)); }
    setBusy(false);
  }
  async function guardar() {
    if (!tid) return;
    setBusy(true); setMsg("");
    try {
      await api.putTipo(tid, yaml);
      // Los ejemplos de captura son buenos ejemplos del tipo -> opcionalmente quedan como
      // referencias (los embebe y calibra el template) en el mismo paso.
      if (usarRefs && files.length) {
        await run(`Agregar ${files.length} referencia(s) de calibración`,
          async () => { for (const f of files) await api.addRef(tid, f); },
          ["Embebiendo ejemplos como referencias…", "Calibrando el template…"]);
      }
      onSaved();
    } catch (e) { setMsg("Error: " + errMsg(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-side" onClick={(e) => e.stopPropagation()}>
        <div className="modal-h"><b>Nuevo template (desde uno o varios ejemplos)</b><button className="btn btn-ghost" onClick={onClose}>✕</button></div>
        <div className="modal-b" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label className="dropzone" style={{ padding: 18 }}>
            <input type="file" multiple hidden onChange={(e) => setFiles(Array.from(e.target.files || []))} />
            <Upload size={24} color="var(--teal)" />
            <div className="t" style={{ fontSize: 13 }}>{files.length ? `${files.length} archivo(s) elegido(s)` : "Subí uno o varios ejemplos del mismo tipo"}</div>
            <div className="s">Con varios ejemplos las reglas se consolidan (generalizan, no se sobreajustan)</div>
          </label>
          {files.length > 0 && (
            <div className="faint mono" style={{ fontSize: 11 }}>{files.map((f) => f.name).join(" · ")}</div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <input className="input" placeholder="tipo_doc (id, opcional)" value={tid} onChange={(e) => setTid(e.target.value)} />
            <input className="input" placeholder="Nombre (opcional)" value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 14, fontSize: 12.5 }}>
            <label><input type="radio" checked={modo === "ejemplo"} onChange={() => setModo("ejemplo")} /> Ejemplos del tipo</label>
            <label><input type="radio" checked={modo === "especificacion"} onChange={() => setModo("especificacion")} /> Especificación que define el tipo</label>
          </div>
          <button className="btn btn-ghost" disabled={!files.length || busy} onClick={analizar}>
            {busy ? "Analizando…" : files.length > 1 ? `🔎 Analizar ${files.length} ejemplos` : "🔎 Analizar"}
          </button>

          {cob.length > 0 && (
            <div className="card" style={{ padding: 10 }}>
              <div className="eyebrow">COBERTURA DE REGLAS · cuántos ejemplos cumple cada patrón</div>
              {cob.map((c, i) => {
                const ok = !c.error && c.n === c.total;
                const col = c.error ? "var(--red)" : ok ? "var(--green)" : "var(--amber)";
                return (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, padding: "3px 0" }}>
                    <span><b>{c.campo}</b> <span className="faint mono">{c.patron}</span></span>
                    <span className="mono" style={{ color: col }}>{c.error ? "patrón inválido" : `${c.n}/${c.total}`}</span>
                  </div>
                );
              })}
              <div className="faint" style={{ fontSize: 10.5, marginTop: 4 }}>Los patrones que no cumplen todos los ejemplos conviene revisarlos/relajarlos.</div>
            </div>
          )}

          {yaml && (
            <>
              <textarea className="input mono" style={{ minHeight: 260, fontSize: 12 }} value={yaml} onChange={(e) => setYaml(e.target.value)} />
              <input className="input" placeholder="Guardar como (id)" value={tid} onChange={(e) => setTid(e.target.value)} />
              {files.length > 0 && (
                <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 12.5 }}>
                  <input type="checkbox" checked={usarRefs} onChange={(e) => setUsarRefs(e.target.checked)} style={{ marginTop: 2 }} />
                  <span>Usar estos <b>{files.length}</b> ejemplo(s) también como <b>referencias</b> (calibración) — el template nace calibrado y el score arranca activo.</span>
                </label>
              )}
              <button className="btn btn-primary" disabled={!tid || busy} onClick={guardar}>
                {busy ? "Creando…" : usarRefs && files.length ? `Crear template + ${files.length} referencia(s)` : "Crear template"}
              </button>
            </>
          )}
          {msg && <span style={{ color: "var(--red-ink)" }}>{msg}</span>}
        </div>
      </div>
    </div>
  );
}

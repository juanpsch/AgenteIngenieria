import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type ReglaStat } from "../api/client";
import { ChevronRight, ChevronDown } from "lucide-react";

// Observatorio de reglas: planilla de todas las reglas con su estadística de cumplimiento, facetada,
// para analizar qué regla afecta a qué familias/docs y revisar el feedback humano.
const EJES: [string, string][] = [["organizacion", "Empresa"], ["tipo", "Tipo"], ["disciplina", "Disciplina"], ["jurisdiccion", "Jurisdicción"]];
const SEV_CLS: Record<string, string> = { bloqueante: "mat-red", mayor: "mat-amber", menor: "mat-neutral", observacion: "mat-ok" };
const FB: [string, string, string][] = [["de_acuerdo", "👍", "de acuerdo"], ["no_aplica", "🚫", "no aplica"], ["regla_mal", "⚠", "regla mal"]];

function PctBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="faint">—</span>;
  const color = pct >= 80 ? "var(--green)" : pct >= 50 ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 6, background: "var(--line)", borderRadius: 3, overflow: "hidden", minWidth: 44 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color }} />
      </div>
      <span className="mono" style={{ fontSize: 11, width: 38, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

function FeedbackChips({ fb }: { fb: Record<string, number> }) {
  if (!FB.some(([k]) => fb[k])) return <span className="faint">—</span>;
  return <>{FB.filter(([k]) => fb[k]).map(([k, e, t]) => (
    <span key={k} className={`chip ${k === "regla_mal" ? "mat-amber" : k === "de_acuerdo" ? "mat-ok" : "mat-neutral"}`} title={t} style={{ fontSize: 10 }}>{e} {fb[k]}</span>
  ))}</>;
}

export function Reglas() {
  const [data, setData] = useState<ReglaStat[]>([]);
  const [norma, setNorma] = useState("");
  const [filtro, setFiltro] = useState<{ eje: string; valor: string }>({ eje: "", valor: "" });
  const [q, setQ] = useState("");
  const [soloDatos, setSoloDatos] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => { api.reglasEstadisticas().then(setData).catch(() => {}); }, []);

  const normas = useMemo(() => [...new Set(data.map((r) => r.norma_id).filter(Boolean))].sort() as string[], [data]);
  const valoresDe = (eje: string) => [...new Set(data.flatMap((r) => r.familias.map((f) => f.facetas?.[eje])).filter(Boolean))].sort() as string[];

  const filtradas = useMemo(() => data.filter((r) => {
    if (soloDatos && !r.n) return false;
    if (norma && r.norma_id !== norma) return false;
    if (filtro.eje && filtro.valor && !r.familias.some((f) => f.facetas?.[filtro.eje] === filtro.valor)) return false;
    if (q && !`${r.descripcion || ""} ${r.req_id}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }).sort((a, b) => (b.feedback.regla_mal || 0) - (a.feedback.regla_mal || 0) || b.n - a.n), [data, norma, filtro, q, soloDatos]);

  const COLS = "26px 2.4fr 1.1fr 0.8fr 56px 1.4fr 1.1fr";
  return (
    <div className="ct-fade">
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <select value={norma} onChange={(e) => setNorma(e.target.value)} style={{ fontSize: 12, padding: "4px 6px" }}>
          <option value="">Todas las normas</option>
          {normas.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <span className="faint" style={{ fontSize: 12 }}>Faceta:</span>
        <select value={filtro.eje} onChange={(e) => setFiltro({ eje: e.target.value, valor: "" })} style={{ fontSize: 12, padding: "4px 6px" }}>
          <option value="">(eje)</option>
          {EJES.map(([e, l]) => <option key={e} value={e}>{l}</option>)}
        </select>
        {filtro.eje && (
          <select value={filtro.valor} onChange={(e) => setFiltro({ ...filtro, valor: e.target.value })} style={{ fontSize: 12, padding: "4px 6px" }}>
            <option value="">(todos)</option>
            {valoresDe(filtro.eje).map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        )}
        <input placeholder="Buscar regla…" value={q} onChange={(e) => setQ(e.target.value)} style={{ fontSize: 12, padding: "5px 8px", minWidth: 160 }} />
        <label className="faint" style={{ fontSize: 12, display: "flex", gap: 5, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={soloDatos} onChange={(e) => setSoloDatos(e.target.checked)} /> solo con datos
        </label>
        <span className="faint" style={{ marginLeft: "auto", fontSize: 12 }}>{filtradas.length} reglas</span>
      </div>

      <div className="table">
        <div className="tr head" style={{ gridTemplateColumns: COLS }}>
          <span></span><span>REGLA</span><span>NORMA</span><span>SEVERIDAD</span><span>DOCS</span><span>CUMPLIMIENTO</span><span>FEEDBACK</span>
        </div>
        {filtradas.map((r) => (
          <Fragment key={r.req_id}>
            <div className="tr row" role="button" tabIndex={0} style={{ gridTemplateColumns: COLS }}
              onClick={() => setOpen(open === r.req_id ? null : r.req_id)}
              onKeyDown={(e) => { if (e.key === "Enter") setOpen(open === r.req_id ? null : r.req_id); }}>
              <span style={{ color: "var(--muted)" }}>{open === r.req_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
              <span><b>{r.descripcion || r.id}</b><div className="faint mono" style={{ fontSize: 10 }}>{r.req_id}</div></span>
              <span className="muted" style={{ fontSize: 12 }}>{r.norma_ref || r.norma_id || "—"}</span>
              <span>{r.severidad && <span className={`chip ${SEV_CLS[r.severidad] || "mat-neutral"}`} style={{ fontSize: 9.5 }}>{r.severidad}</span>}</span>
              <span className="mono">{r.n || "—"}</span>
              <span><PctBar pct={r.pct_cumple} /></span>
              <span style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
                <FeedbackChips fb={r.feedback} />
                {FB.some(([k]) => r.feedback_amplio?.[k]) && (
                  <span className="chip mat-info" style={{ fontSize: 9 }} title="Hay juicios a nivel norma/global: se reusan en todas las familias que usan la regla">↗ norma</span>
                )}
              </span>
            </div>
            {open === r.req_id && (
              <div className="tr" style={{ background: "var(--bg)" }}>
                <span style={{ gridColumn: "1 / -1" }}>
                  {r.familias.length ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "6px 2px" }}>
                      {r.familias.map((f) => (
                        <div key={f.tipo_doc} style={{ display: "grid", gridTemplateColumns: "1.8fr 1.8fr 56px 1.4fr 1.1fr", gap: 8, alignItems: "center" }}>
                          <span style={{ fontSize: 12 }}><b>{f.nombre}</b></span>
                          <span>{Object.entries(f.facetas).map(([e, v]) => <span key={e} className="chip mat-neutral" style={{ fontSize: 9 }}>{e}:{v}</span>) || <span className="faint">—</span>}</span>
                          <span className="mono" style={{ fontSize: 11 }}>{f.n}</span>
                          <span><PctBar pct={f.pct_cumple} /></span>
                          <span><FeedbackChips fb={f.feedback} /></span>
                        </div>
                      ))}
                    </div>
                  ) : <span className="faint" style={{ fontSize: 12 }}>Sin evaluaciones registradas todavía.</span>}
                </span>
              </div>
            )}
          </Fragment>
        ))}
        {!filtradas.length && <div className="tr"><span className="faint">No hay reglas con esos filtros.</span></div>}
      </div>
    </div>
  );
}

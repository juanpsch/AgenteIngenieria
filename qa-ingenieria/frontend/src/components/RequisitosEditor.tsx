import { useEffect, useMemo, useState } from "react";
import { api, type CatalogoRequisito } from "../api/client";
import { errMsg } from "../design/tokens";

const SEV_CLS: Record<string, string> = { bloqueante: "mat-red", mayor: "mat-amber", menor: "mat-neutral", observacion: "mat-ok" };

/** Asigna a una familia (template) qué REQUISITOS chequeables exige, desde el catálogo de normas.
 *  Marca los "sugeridos por disciplina" y guarda la lista explícita en `revision.requisitos`. */
export function RequisitosEditor({ tipoDoc, disciplinas, resueltosIniciales, onSaved }: {
  tipoDoc: string; disciplinas?: string[]; resueltosIniciales?: string[]; onSaved?: () => void;
}) {
  const [cat, setCat] = useState<CatalogoRequisito[]>([]);
  const [asig, setAsig] = useState<Set<string>>(new Set(resueltosIniciales || []));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.catalogoRequisitos().then(setCat).catch(() => {}); }, []);

  const disc = useMemo(() => new Set((disciplinas || []).map((d) => d.toLowerCase())), [disciplinas]);
  const sugerido = (q: CatalogoRequisito) => {
    const ds = q.disciplinas;
    return !!ds && (ds.includes("*") || ds.some((x) => disc.has(String(x).toLowerCase())));
  };
  const porNorma = useMemo(() => {
    const m: Record<string, CatalogoRequisito[]> = {};
    for (const q of cat) (m[q.norma_nombre || q.norma_id] ||= []).push(q);
    return m;
  }, [cat]);

  const toggle = (id: string) => setAsig((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const asignarSugeridos = () => setAsig((s) => { const n = new Set(s); cat.filter(sugerido).forEach((q) => n.add(q.req_id)); return n; });

  async function guardar() {
    setBusy(true); setMsg("");
    try { await api.putRequisitos(tipoDoc, [...asig]); setMsg("Guardado ✓"); onSaved?.(); }
    catch (e) { setMsg("Error: " + errMsg(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div className="dim-h" style={{ margin: 0 }}>Requisitos de revisión (cumplimiento)</div>
        <span className="chip mat-neutral" style={{ fontSize: 10 }}>{asig.size} asignados</span>
        <button className="btn btn-ghost" style={{ marginLeft: "auto", padding: "4px 9px" }} onClick={asignarSugeridos}>
          Asignar sugeridos {disciplinas?.length ? `(${disciplinas.join("/")})` : ""}
        </button>
      </div>
      <div className="faint" style={{ fontSize: 11.5, margin: "2px 0 8px" }}>
        Tildá qué requisitos exige esta familia (de una o varias normas). Los <b>sugeridos</b> salen de la
        disciplina del template; el aprendizaje refinará esto con los casos aprobados.
      </div>

      {Object.keys(porNorma).sort().map((norma) => (
        <div key={norma} style={{ borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 12.5, marginBottom: 4 }}>{norma}</div>
          {porNorma[norma].map((q) => (
            <label key={q.req_id} style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "4px 0", cursor: "pointer" }}>
              <input type="checkbox" checked={asig.has(q.req_id)} onChange={() => toggle(q.req_id)} style={{ marginTop: 3 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", fontSize: 12.5 }}>
                  <span>{q.descripcion || q.id}</span>
                  {q.severidad && <span className={`chip ${SEV_CLS[q.severidad] || "mat-neutral"}`} style={{ fontSize: 9.5 }}>{q.severidad}</span>}
                  {sugerido(q) && <span className="chip mat-ok" style={{ fontSize: 9.5 }}>sugerido</span>}
                  <span className="faint mono" style={{ fontSize: 9.5 }}>{q.tipo}</span>
                </div>
              </div>
            </label>
          ))}
        </div>
      ))}
      {!cat.length && <div className="faint">Catálogo de requisitos vacío (definí normas en knowledge/normas/).</div>}

      <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center" }}>
        <button className="btn btn-primary" disabled={busy} onClick={guardar}>{busy ? "Guardando…" : "Guardar requisitos"}</button>
        {msg && <span className={msg.startsWith("Error") ? "" : "muted"} style={msg.startsWith("Error") ? { color: "var(--red-ink)" } : undefined}>{msg}</span>}
      </div>
    </div>
  );
}

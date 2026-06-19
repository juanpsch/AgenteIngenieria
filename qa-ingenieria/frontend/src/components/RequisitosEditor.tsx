import { useEffect, useMemo, useState } from "react";
import { api, type CatalogoRequisito, type Perfil, type SugerenciaReq, type SugerenciasRequisitos } from "../api/client";
import { errMsg } from "../design/tokens";

const SEV_CLS: Record<string, string> = { bloqueante: "mat-red", mayor: "mat-amber", menor: "mat-neutral", observacion: "mat-ok" };

/** Asigna a una familia (template) qué REQUISITOS chequeables exige, desde el catálogo de normas.
 *  Marca los "sugeridos por disciplina" y guarda la lista explícita en `revision.requisitos`. */
export function RequisitosEditor({ tipoDoc, disciplinas, resueltosIniciales, onSaved }: {
  tipoDoc: string; disciplinas?: string[]; resueltosIniciales?: string[]; onSaved?: () => void;
}) {
  const [cat, setCat] = useState<CatalogoRequisito[]>([]);
  const [asig, setAsig] = useState<Set<string>>(new Set(resueltosIniciales || []));
  const [sug, setSug] = useState<SugerenciasRequisitos | null>(null);
  const [perfiles, setPerfiles] = useState<Perfil[]>([]);
  const [perfilSel, setPerfilSel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.catalogoRequisitos().then(setCat).catch(() => {}); }, []);
  useEffect(() => { api.sugerenciasRequisitos(tipoDoc).then(setSug).catch(() => {}); }, [tipoDoc]);
  useEffect(() => { api.perfiles().then(setPerfiles).catch(() => {}); }, []);

  function agregarPerfil() {
    const p = perfiles.find((x) => x.id === perfilSel);
    if (p) setAsig((a) => new Set([...a, ...p.requisitos]));
  }

  // aplica una sugerencia (la saca de la lista y muta el set asignado)
  function aplicar(grupo: "agregar" | "quitar" | "prior_disciplina", s: SugerenciaReq) {
    setAsig((a) => { const n = new Set(a); grupo === "quitar" ? n.delete(s.req_id) : n.add(s.req_id); return n; });
    setSug((prev) => prev ? { ...prev, [grupo]: prev[grupo].filter((x) => x.req_id !== s.req_id) } : prev);
  }

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

      {perfiles.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <span className="faint" style={{ fontSize: 11.5 }}>Perfil de cumplimiento (proyecto):</span>
          <select className="select" style={{ width: "auto", padding: "4px 8px", fontSize: 12 }} value={perfilSel} onChange={(e) => setPerfilSel(e.target.value)}>
            <option value="">Elegí un perfil…</option>
            {perfiles.map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.jurisdiccion ? ` · ${p.jurisdiccion}` : ""} ({p.requisitos.length})</option>)}
          </select>
          <button className="btn btn-ghost" style={{ padding: "4px 9px" }} disabled={!perfilSel} onClick={agregarPerfil}>+ agregar requisitos del perfil</button>
        </div>
      )}

      {sug && (sug.agregar.length + sug.quitar.length + sug.prior_disciplina.length > 0) && (
        <div style={{ border: "1px solid var(--teal)", background: "var(--teal-wash)", borderRadius: 8, padding: 10, marginBottom: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 12.5, marginBottom: 4 }}>Sugerencias del aprendizaje</div>
          {([["agregar", "Agregar"], ["quitar", "Quitar"], ["prior_disciplina", "Por disciplina"]] as const).map(([k, lbl]) =>
            sug[k].length ? (
              <div key={k} style={{ marginTop: 4 }}>
                <span className="faint" style={{ fontSize: 10.5 }}>{lbl}:</span>
                {sug[k].map((s) => (
                  <div key={s.req_id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 12 }}>
                    <button className={`btn ${k === "quitar" ? "btn-red-o" : "btn-green"}`} style={{ padding: "2px 8px", fontSize: 11 }}
                      onClick={() => aplicar(k, s)}>{k === "quitar" ? "− quitar" : "+ agregar"}</button>
                    <span style={{ flex: 1, minWidth: 0 }}>{s.descripcion} <span className="faint">· {s.evidencia}</span></span>
                    {s.norma_ref && <span className="chip mat-neutral" style={{ fontSize: 9.5 }}>{s.norma_ref}</span>}
                  </div>
                ))}
              </div>
            ) : null,
          )}
          <div className="faint" style={{ fontSize: 10.5, marginTop: 6 }}>Aplicar solo ajusta la selección; recordá <b>Guardar</b> abajo.</div>
        </div>
      )}

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

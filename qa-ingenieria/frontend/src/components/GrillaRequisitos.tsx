import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api, type EstadoRevision, type Hallazgo, type Juicio } from "../api/client";
import { errMsg } from "../design/tokens";

const EST_BADGE: Record<EstadoRevision, string> = { ok: "b-pass", fallo: "b-fail", advertencia: "b-warn", no_verificable: "b-info" };
const EST_GLYPH: Record<EstadoRevision, string> = { ok: "✓", fallo: "✕", advertencia: "!", no_verificable: "?" };
const DIM_LABEL: Record<string, string> = { legibilidad: "Legibilidad", norma: "Norma / nomenclatura", contenido: "Contenido", consistencia: "Consistencia" };
const SEV_CLS: Record<string, string> = { bloqueante: "mat-red", mayor: "mat-amber", menor: "mat-neutral", observacion: "mat-ok" };
const NORMA_FALLBACK = "General / interno";
const JUICIOS: { v: Juicio; label: string; cls: string; hint: string }[] = [
  { v: "de_acuerdo", label: "de acuerdo", cls: "mat-ok", hint: "el check es válido en esta familia" },
  { v: "no_aplica", label: "no aplica", cls: "mat-neutral", hint: "esta regla no corresponde a esta familia" },
  { v: "regla_mal", label: "regla mal", cls: "mat-amber", hint: "el check está errado (falso positivo/negativo)" },
];

function roll(hs: Hallazgo[]) {
  return { ok: hs.filter((h) => h.estado === "ok").length, tot: hs.length, fail: hs.some((h) => h.estado === "fallo") };
}

/** Grilla jerárquica Norma → Dimensión → requisito (plegable), con el resultado automático y un
 *  JUICIO HUMANO opcional por regla (de acuerdo / no aplica / regla mal) que retroalimenta a la regla. */
export function GrillaRequisitos({ hallazgos, threadId, feedbackInicial }: {
  hallazgos: Hallazgo[]; threadId?: string; feedbackInicial?: Record<string, { juicio: Juicio; nota: string | null }>;
}) {
  const [colapsado, setColapsado] = useState<Set<string>>(new Set());
  const [fb, setFb] = useState<Record<string, Juicio>>(() =>
    Object.fromEntries(Object.entries(feedbackInicial || {}).map(([k, v]) => [k, v.juicio])));
  const [err, setErr] = useState("");

  const tree = useMemo(() => {
    const t: Record<string, Record<string, Hallazgo[]>> = {};
    for (const h of hallazgos || []) {
      const nr = h.norma_ref || NORMA_FALLBACK;
      (t[nr] ||= {});
      (t[nr][h.dimension || "otros"] ||= []).push(h);
    }
    return t;
  }, [hallazgos]);

  const toggle = (k: string) => setColapsado((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });

  async function juzgar(reqId: string, j: Juicio) {
    if (!threadId || fb[reqId] === j) return;   // re-clic del mismo juicio: no-op (no hay borrado)
    setErr("");
    setFb((p) => ({ ...p, [reqId]: j }));
    try { await api.requisitoFeedback(threadId, reqId, j); }
    catch (e) { setErr(errMsg(e)); }
  }

  if (!hallazgos?.length) return null;
  return (
    <div className="card">
      <div className="dim-h">Requisitos (por norma · dimensión)</div>
      <div className="faint" style={{ fontSize: 11.5, margin: "2px 0 8px" }}>
        Resultado automático por requisito. Opcional: marcá <b>tu juicio</b> por regla — retroalimenta a la regla, no solo al documento.
      </div>
      {err && <div style={{ color: "var(--red-ink)", marginBottom: 8 }}>{err}</div>}

      {Object.keys(tree).sort().map((norma) => {
        const dims = tree[norma];
        const todas = Object.values(dims).flat();
        const r = roll(todas);
        const nk = `n:${norma}`;
        const colN = colapsado.has(nk);
        return (
          <div key={norma} style={{ borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 8 }}>
            <div role="button" onClick={() => toggle(nk)} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontWeight: 600 }}>
              {colN ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
              <span>{norma}</span>
              <span className={`chip ${r.fail ? "mat-red" : "mat-ok"}`} style={{ marginLeft: "auto", fontSize: 10 }}>{r.ok}/{r.tot} ✓</span>
            </div>

            {!colN && Object.keys(dims).map((dim) => {
              const hs = dims[dim]; const dr = roll(hs); const dk = `d:${norma}:${dim}`; const colD = colapsado.has(dk);
              return (
                <div key={dim} style={{ marginLeft: 14, marginTop: 6 }}>
                  <div role="button" onClick={() => toggle(dk)} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                    {colD ? <ChevronRight size={13} /> : <ChevronDown size={13} />}
                    <span className="eyebrow" style={{ margin: 0 }}>{DIM_LABEL[dim] || dim}</span>
                    <span className="faint" style={{ fontSize: 10.5, marginLeft: "auto" }}>{dr.ok}/{dr.tot}</span>
                  </div>
                  {!colD && hs.map((h, i) => (
                    <div key={h.req_id ?? h.check_id ?? i} className="check" style={{ marginLeft: 16, paddingTop: 6 }}>
                      <div className={`badge ${EST_BADGE[h.estado]}`} title={h.estado}>{EST_GLYPH[h.estado]}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="lab" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          <span>{h.razonamiento || h.check_id}</span>
                          {h.severidad && <span className={`chip ${SEV_CLS[h.severidad] || "mat-neutral"}`} style={{ fontSize: 9.5 }}>{h.severidad}</span>}
                          {h.estado_previo && <span className="chip mat-info" style={{ fontSize: 9.5 }} title={h.nota_vlm || ""}>ⓘ verificado por IA</span>}
                          {h.ubicacion?.pagina && <span className="faint" style={{ fontSize: 10, fontWeight: 400 }}>pág {h.ubicacion.pagina}</span>}
                        </div>
                        {h.evidencia && <div className="det">{h.evidencia}</div>}
                        {h.estado_previo && (
                          <div className="det" style={{ color: "var(--info-ink, #2563eb)" }}>
                            ⓘ El VLM cambió esto: {EST_GLYPH[h.estado_previo]} {h.estado_previo} → {EST_GLYPH[h.estado]} {h.estado}.{h.nota_vlm ? ` ${h.nota_vlm}` : ""}
                          </div>
                        )}
                        {/* Juicio humano por regla (solo requisitos con id global) */}
                        {h.req_id && threadId && (
                          <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 5, flexWrap: "wrap" }}>
                            <span className="faint" style={{ fontSize: 10.5 }}>mi juicio:</span>
                            {JUICIOS.map((j) => (
                              <button key={j.v} title={j.hint} onClick={() => juzgar(h.req_id!, j.v)}
                                className={`chip ${fb[h.req_id!] === j.v ? j.cls : "mat-neutral"}`}
                                style={{ cursor: "pointer", fontSize: 10, opacity: fb[h.req_id!] && fb[h.req_id!] !== j.v ? 0.5 : 1, border: fb[h.req_id!] === j.v ? "1px solid var(--ink)" : undefined }}>
                                {j.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type Historial as H, type Veredicto, type ValidarResp } from "../api/client";
import { VeredictoChip } from "../components/ui";
import { ResultadoDetalle } from "../components/ResultadoDetalle";
import { useActivity } from "../components/Activity";
import { errMsg, maturityLabel } from "../design/tokens";
import { ArrowLeft, Check, X } from "lucide-react";

function Metric({ n, l, color }: { n: number | string; l: string; color?: string }) {
  return <div className="metric"><div className="n" style={{ color }}>{n}</div><div className="l">{l}</div></div>;
}

type Caso = ValidarResp & { decision: string | null };

export function Historial() {
  const [h, setH] = useState<H | null>(null);
  const [caso, setCaso] = useState<Caso | null>(null);
  const [doc, setDoc] = useState<string>("");
  const [yaPromovido, setYaPromovido] = useState(false);
  const [promote, setPromote] = useState(true);
  const [promoted, setPromoted] = useState<{ refs_count: number; maturity: string } | null>(null);
  const [negativoOk, setNegativoOk] = useState<number | null>(null);
  const [decidiendo, setDecidiendo] = useState(false);
  const [err, setErr] = useState("");
  const { run } = useActivity();

  useEffect(() => { api.historial().then(setH).catch(() => {}); }, []);

  async function abrir(threadId: string, docName: string, promovido: boolean) {
    setErr(""); setDoc(docName); setYaPromovido(promovido); setPromoted(null); setNegativoOk(null); setPromote(true); setCaso(null);
    try {
      const c = await run(`Abrir análisis: ${docName}`, () => api.getCaso(threadId), ["Reconstruyendo el análisis…"]);
      setCaso(c);
    } catch (e) { setErr("No se pudo abrir el detalle: " + errMsg(e)); }
  }

  async function decidir(d: "approved" | "rejected") {
    if (!caso || decidiendo) return;
    setErr(""); setDecidiendo(true); setPromoted(null); setNegativoOk(null); setYaPromovido(false);  // override limpio
    try {
      await api.decision(caso.thread_id, d);
      // Re-leer: al aprobar un caso admitido se dispara la revisión de contenido.
      setCaso(await run("Aplicar decisión", () => api.getCaso(caso.thread_id), ["Registrando decisión y revisando…"]));
    } catch (e) { setErr("No se pudo registrar la decisión: " + errMsg(e)); }
    finally { setDecidiendo(false); }
  }
  async function confirmarPromo() {
    if (!caso) return;
    setErr("");
    try { setPromoted(await api.promover(caso.tipo_doc, caso.thread_id, promote)); }
    catch (e) { setErr("No se pudo promover: " + errMsg(e)); }
  }
  async function usarNegativo() {
    if (!caso) return;
    setErr("");
    try { const r = await run("Usar como contra-ejemplo", () => api.agregarNegativo(caso.thread_id)); setNegativoOk(r.negativos_count); }
    catch (e) { setErr("No se pudo guardar el contra-ejemplo: " + errMsg(e)); }
  }

  // --- Detalle de un análisis pasado ---
  if (caso) {
    const dec = caso.decision === "approved" ? { t: "Aprobado por un humano", c: "var(--green-ink)" }
      : caso.decision === "rejected" ? { t: "Rechazado por un humano", c: "var(--red-ink)" }
      : { t: "Sin decisión humana registrada", c: "var(--muted)" };
    return (
      <div className="ct-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <button className="btn btn-ghost" style={{ alignSelf: "flex-start" }} onClick={() => setCaso(null)}><ArrowLeft size={15} /> Volver al historial</button>
        <ResultadoDetalle res={caso} fileName={doc} />

        {/* Panel de revisión: un SENIOR puede sobrescribir la decisión del junior, y promover / marcar contra-ejemplo */}
        <div className="card">
          <div className="dim-h">Decisión de admisión (revisión)</div>
          {err && <div style={{ color: "var(--red-ink)", marginBottom: 10 }}>{err}</div>}
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
            Decisión actual: <b style={{ color: dec.c }}>{dec.t}</b>. Podés <b>sobrescribirla</b>.
          </div>
          <div className="row-actions" style={{ marginBottom: 10 }}>
            <button className="btn btn-red-o" disabled={decidiendo} onClick={() => decidir("rejected")}><X size={15} /> No admitir</button>
            <button className="btn btn-green" disabled={decidiendo} onClick={() => decidir("approved")}><Check size={15} /> Admitir</button>
          </div>

          {caso.decision === "approved" && (
            yaPromovido ? <div style={{ color: "var(--teal)" }}>✓ Ya promovido a referencia</div>
            : promoted ? <div style={{ color: "var(--green-ink)" }}>
                ✓ {promote ? `Agregado como referencia · el template ahora tiene ${promoted.refs_count} ejemplos (${maturityLabel(promoted.maturity)})` : "Confirmado sin promover"}
              </div>
            : <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="faint" style={{ fontSize: 12 }}>Promover este documento a referencia mejora la precisión del template.</div>
                <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input type="checkbox" checked={promote} onChange={(e) => setPromote(e.target.checked)} />
                  Usar este documento para mejorar el template (positivo)
                </label>
                <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={confirmarPromo}>
                  {promote ? "Confirmar y promover" : "Confirmar sin promover"}
                </button>
              </div>
          )}

          {caso.decision === "rejected" && (
            negativoOk != null
              ? <div style={{ color: "var(--green-ink)", fontSize: 12 }}>✓ Guardado como contra-ejemplo ({negativoOk} en este tipo)</div>
              : (caso.veredicto === "valido" || caso.veredicto === "revision_manual") && (
                  <div className="faint" style={{ fontSize: 12 }}>
                    El modelo lo daba admisible. ¿Usarlo como <b>contra-ejemplo</b> para que no se admitan parecidos?
                    <button className="btn btn-ghost" style={{ marginLeft: 8, padding: "3px 9px" }} onClick={usarNegativo}>Usar como contra-ejemplo</button>
                  </div>
                )
          )}
        </div>
      </div>
    );
  }

  // --- Lista ---
  if (!h) return <div className="faint">Cargando…</div>;
  const m = h.metricas;
  return (
    <div className="ct-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="card" style={{ borderColor: "var(--red-border)", color: "var(--red-ink)" }}>{err}</div>}
      <div className="metrics">
        <Metric n={m.validados} l="Validados" />
        <Metric n={`${m.aprobacion_pct}%`} l="% de aprobación" color="var(--green)" />
        <Metric n={m.pendientes} l="Pendientes de revisión" color="var(--amber)" />
        <Metric n={m.promovidos} l="Promovidos a referencia" color="var(--teal)" />
      </div>
      <div className="table">
        <div className="tr head" style={{ gridTemplateColumns: "1.6fr 1.4fr 1.1fr .7fr 1fr" }}>
          <span>DOCUMENTO</span><span>TEMPLATE</span><span>VEREDICTO</span><span>SCORE</span><span>FECHA</span>
        </div>
        {h.items.map((it) => (
          <div key={it.thread_id} className="tr row" role="button" tabIndex={0}
            style={{ gridTemplateColumns: "1.6fr 1.4fr 1.1fr .7fr 1fr" }}
            title="Ver el detalle del análisis"
            onClick={() => abrir(it.thread_id, it.doc, !!it.promovido_a_ref)}
            onKeyDown={(e) => { if (e.key === "Enter") abrir(it.thread_id, it.doc, !!it.promovido_a_ref); }}>
            <span className="mono" style={{ fontSize: 12 }}>{it.doc}{it.promovido_a_ref ? "  ↑ref" : ""}</span>
            <span className="muted">{it.tipo_doc}</span>
            <span><VeredictoChip v={it.veredicto as Veredicto} /></span>
            <span className="mono">{it.score ?? "—"}</span>
            <span className="faint" style={{ fontSize: 11 }}>{it.fecha}</span>
          </div>
        ))}
        {!h.items.length && <div className="tr"><span className="faint">Sin validaciones todavía.</span></div>}
      </div>
      <div className="faint" style={{ fontSize: 11.5 }}>Hacé clic en una fila para ver el detalle del análisis (veredicto, score, checks y preview).</div>
    </div>
  );
}

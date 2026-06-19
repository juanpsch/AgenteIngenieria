import { api, type ValidarResp, type VarianteSugerida } from "../api/client";
import { VerdictBanner } from "./ui";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { Desglose } from "./Desglose";
import { PaginasViewer } from "./PaginasViewer";
import { InformeZonas } from "./InformeZonas";
import { RevisionSection } from "./RevisionSection";
import { useActivity } from "./Activity";
import { errMsg } from "../design/tokens";
import { useState } from "react";
import { Lightbulb } from "lucide-react";

/** Evidencia de un cotejo (en vivo o reconstruida del historial): veredicto, desglose del score,
 *  informe por zona, preview multipágina con overlays, checks por dimensión, y feedback de reglas.
 *  Solo lectura; la decisión/promoción la maneja la pantalla que lo usa. */
export function ResultadoDetalle({ res, fileName }: { res: ValidarResp; fileName?: string }) {
  const fname = fileName || res.documento_panel?.["titulo"] || res.tipo_doc || "documento";
  const ident = (res.checks || []).filter((c) => c.dimension === "identidad");
  const compl = (res.checks || []).filter((c) => c.dimension === "completitud");
  const imagenes = res.imagenes?.length ? res.imagenes : (res.imagen ? [res.imagen] : []);

  const previewCard = (
    <PaginasViewer imagenes={imagenes} zonas={res.zonas_resultado || []} cajetinBbox={res.cajetin_bbox} />
  );

  return (
    <>
      <VerdictBanner veredicto={res.veredicto} resumen={res.resumen} fileName={fname} tipo={res.tipo_doc} score={res.score} noConcluyente={res.no_concluyente} />
      <ScoreBreakdown d={res.score_detalle} />
      <InformeZonas zonas={res.zonas_resultado || []} />
      <Desglose ident={ident} compl={compl} preview={previewCard} />
      <FeedbackReglas res={res} />
      {res.revision && <RevisionSection rev={res.revision} imagenes={imagenes} threadId={res.thread_id} />}
      <details className="card" style={{ fontSize: 12.5 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>¿Cómo se compara un documento?</summary>
        <div style={{ color: "var(--muted)", lineHeight: 1.7, marginTop: 8 }}>
          El gate evalúa <b>dos dimensiones independientes</b>. <b>Identidad</b>: un agente decide si el
          documento es el tipo elegido (empresa, tipo y rótulo), un modelo de visión calcula la
          <b> similitud</b> contra los ejemplos de referencia ponderando la <b>zona de identidad</b> y la
          <b> página</b>, y reglas deterministas (p. ej. el código debe coincidir con el nombre de archivo).
          <b> Completitud</b>: se verifican los campos del rótulo (reglas/regex) y las secciones obligatorias.
          El <b>score</b> solo <b>decide</b> cuando el template está <b>calibrado</b>; con pocos ejemplos es
          informativo. El veredicto final siempre lo <b>confirma un humano</b>.
        </div>
      </details>
    </>
  );
}

/** Reglas regex que NO se cumplieron: ofrece proponer una variante (verificada contra el corpus)
 *  y aplicarla, con visto bueno humano. Cierra el loop de aprendizaje del rechazo. */
function FeedbackReglas({ res }: { res: ValidarResp }) {
  const fallidas = (res.checks || []).filter(
    (c) => c.regla_tipo === "regex" && c.patron && c.valor && (c.state === "fail" || c.state === "warn"),
  );
  if (!fallidas.length) return null;
  return (
    <div className="card">
      <div className="dim-h">Reglas que no se cumplieron — ¿deberían pasar?</div>
      <div className="faint" style={{ fontSize: 11.5, marginBottom: 4 }}>
        Si el documento es correcto, proponé una variante del patrón. Se <b>verifica contra tus
        ejemplos válidos</b> antes de ofrecerla; vos decidís si la aplicás.
      </div>
      {fallidas.map((c, i) => (
        <ReglaFallida key={i} tipo={res.tipo_doc} campo={c.campo!} patron={c.patron!} valor={c.valor!} />
      ))}
    </div>
  );
}

function ReglaFallida({ tipo, campo, patron, valor }: { tipo: string; campo: string; patron: string; valor: string }) {
  const { run } = useActivity();
  const [prop, setProp] = useState<VarianteSugerida | null>(null);
  const [aplicado, setAplicado] = useState(false);
  const [err, setErr] = useState("");

  async function proponer() {
    setErr("");
    try {
      setProp(await run(`Proponer variante para «${campo}»`, () => api.sugerirVariante(tipo, campo, valor),
        ["Reuniendo ejemplos del corpus…", "Proponiendo y verificando la regex…"]));
    } catch (e) { setErr(errMsg(e)); }
  }
  async function aplicar() {
    if (!prop) return;
    setErr("");
    try { await api.aplicarRegla(tipo, campo, prop.patron); setAplicado(true); }
    catch (e) { setErr(errMsg(e)); }
  }

  return (
    <div style={{ borderTop: "1px solid var(--line)", padding: "8px 0", fontSize: 12.5 }}>
      <div><b>{campo}</b>: <span className="mono">«{valor}»</span> no cumple <span className="mono faint">{patron}</span></div>
      {!prop && !aplicado && (
        <button className="btn btn-ghost" style={{ marginTop: 6, padding: "4px 9px" }} onClick={proponer}><Lightbulb size={13} /> Proponer variante</button>
      )}
      {prop && !aplicado && (
        <div style={{ marginTop: 6 }}>
          <div>Variante propuesta: <span className="mono" style={{ color: "var(--teal)" }}>{prop.patron}</span></div>
          <div className="faint" style={{ fontSize: 11 }}>
            cubre {prop.cubre}/{prop.total} válidos
            {prop.ejemplos_no ? ` · ${prop.ejemplos_no} rechazados en el corpus` : ""}
            {prop.matchea_negativos ? ` · ⚠ matchea ${prop.matchea_negativos} rechazado(s)` : ""}
            {prop.error ? " · ⚠ regex inválida" : ""}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            <button className="btn btn-primary" style={{ padding: "4px 10px" }} disabled={prop.error} onClick={aplicar}>Aplicar al template</button>
            <button className="btn btn-ghost" style={{ padding: "4px 10px" }} onClick={() => setProp(null)}>Descartar</button>
          </div>
        </div>
      )}
      {aplicado && <div style={{ color: "var(--green-ink)", marginTop: 6 }}>✓ Regla actualizada · revalidá para ver el efecto</div>}
      {err && <div style={{ color: "var(--red-ink)", marginTop: 6 }}>{err}</div>}
    </div>
  );
}

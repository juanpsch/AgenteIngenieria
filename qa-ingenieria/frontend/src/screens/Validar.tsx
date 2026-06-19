import { useEffect, useRef, useState } from "react";
import { api, type Tipo, type ValidarResp } from "../api/client";
import { Dropzone } from "../components/ui";
import { ResultadoDetalle } from "../components/ResultadoDetalle";
import { useActivity } from "../components/Activity";
import { maturityLabel, errMsg } from "../design/tokens";
import { ShieldCheck, Check, X } from "lucide-react";

const PASOS = [
  "Extrayendo texto (OCR)", "Detectando rótulo / cajetín", "Cotejando identidad (empresa · tipo)",
  "Verificando campos obligatorios", "Calculando score de similitud",
];
const REV_PASOS = [
  "Extrayendo tablas y secciones (todo el doc)", "Midiendo legibilidad por página",
  "Detectando la norma aplicable", "Chequeando reglas y normas", "Resolviendo veredicto de revisión",
];

export function Validar() {
  const [tipos, setTipos] = useState<Tipo[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [tipoDoc, setTipoDoc] = useState("");
  const [stage, setStage] = useState<"upload" | "processing" | "result">("upload");
  const [step, setStep] = useState(0);
  const [res, setRes] = useState<ValidarResp | null>(null);
  const [decision, setDecision] = useState<null | "approved" | "rejected">(null);
  const [revisarAuto, setRevisarAuto] = useState(true);
  const [revisando, setRevisando] = useState(false);
  const [promote, setPromote] = useState(true);
  const [promoted, setPromoted] = useState<{ refs_count: number; maturity: string } | null>(null);
  const [err, setErr] = useState("");
  const timer = useRef<number>();
  const { run } = useActivity();

  useEffect(() => { api.listTipos().then(setTipos).catch(() => {}); }, []);
  useEffect(() => {
    if (stage !== "processing") return;
    setStep(0);
    timer.current = window.setInterval(() => setStep((s) => Math.min(s + 1, PASOS.length - 1)), 700);
    return () => window.clearInterval(timer.current);
  }, [stage]);

  async function validar() {
    if (!file || !tipoDoc) return;
    setStage("processing"); setErr(""); setDecision(null); setPromoted(null); setRes(null);
    try {
      // Paso 1 — Gate (admisión): rápido, se muestra enseguida.
      const r = await run("Validar (admisión)", () => api.validar(file, tipoDoc, { revisar: false }), PASOS);
      setRes(r); setStage("result");
      // Paso 2 — Revisión de contenido (todo el doc): corre después, con progreso; ya leés el gate.
      if (revisarAuto && r.veredicto === "valido") {
        setRevisando(true);
        try { setRes(await run("Revisión de contenido", () => api.revisarCaso(r.thread_id), REV_PASOS)); }
        catch (e) { setErr("La admisión salió, pero la revisión de contenido falló: " + errMsg(e)); }
        finally { setRevisando(false); }
      }
    } catch (e) { setErr(errMsg(e)); setStage("upload"); }
  }
  async function decidir(d: "approved" | "rejected") {
    if (!res) return;
    setErr("");
    try { await api.decision(res.thread_id, d); setDecision(d); }
    catch (e) { setErr("No se pudo registrar la decisión: " + errMsg(e)); }
  }
  async function revisarAhora() {
    if (!res) return;
    setErr(""); setRevisando(true);
    try { setRes(await run("Revisión de contenido", () => api.revisarCaso(res.thread_id), REV_PASOS)); }
    catch (e) { setErr("No se pudo revisar el contenido: " + errMsg(e)); }
    finally { setRevisando(false); }
  }
  async function confirmarPromo() {
    if (!res) return;
    setErr("");
    try { setPromoted(await api.promover(res.tipo_doc, res.thread_id, promote)); }
    catch (e) { setErr("No se pudo promover: " + errMsg(e)); }
  }
  function reiniciar() {
    setStage("upload"); setFile(null); setTipoDoc("");
    setRes(null); setDecision(null); setPromoted(null); setErr(""); setRevisando(false);
  }

  const tSel = tipos.find((t) => t.tipo_doc === tipoDoc);

  if (stage === "upload")
    return (
      <div className="ct-fade">
        {err && <div className="card" style={{ borderColor: "var(--red-border)", color: "var(--red-ink)", marginBottom: 16 }}>{err}</div>}
        <div className="grid2">
          <div className="card">
            <div className="eyebrow">PASO 1 · DOCUMENTO A VALIDAR</div>
            <div style={{ marginTop: 12 }}>
              <Dropzone file={file} onFile={(f) => { setFile(f); setErr(""); }} size={36}
                title="Seleccioná un archivo para validar"
                subtitle="Arrastrá un PDF o imagen, o hacé clic para buscar" />
            </div>
            <div className="eyebrow" style={{ marginTop: 18 }}>PASO 2 · TEMPLATE DE REFERENCIA</div>
            <select className="select" style={{ marginTop: 10 }} value={tipoDoc} onChange={(e) => setTipoDoc(e.target.value)}>
              <option value="">Elegí un template…</option>
              {tipos.map((t) => (
                <option key={t.tipo_doc} value={t.tipo_doc}>
                  {t.nombre} — {maturityLabel(t.maturity)}
                </option>
              ))}
            </select>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14, fontSize: 12.5 }}>
              <input type="checkbox" checked={revisarAuto} onChange={(e) => setRevisarAuto(e.target.checked)} />
              Revisar contenido al admitir <span className="faint">(Fase 1; si lo destildás, queda pendiente para revisar a mano)</span>
            </label>
            <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} disabled={!file || !tipoDoc} onClick={validar}>
              <ShieldCheck size={16} /> Validar documento
            </button>
          </div>
          <div className="card">
            <div className="eyebrow">CÓMO FUNCIONA EL GATE</div>
            <ol style={{ paddingLeft: 18, color: "var(--muted)", fontSize: 12.5, lineHeight: 1.7, marginBottom: 10 }}>
              <li><b>Identidad</b> — ¿es el tipo elegido? (empresa · tipo · rótulo · similitud visual)</li>
              <li><b>Completitud</b> — ¿están los campos y secciones obligatorios?</li>
              <li><b>Veredicto</b> — 🟢 válido · 🟡 revisión humana · 🔴 inválido.</li>
            </ol>
            <div style={{ display: "flex", gap: 18, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
              <div><div className="mono" style={{ fontSize: 17, color: "var(--green)" }}>96</div><div className="faint" style={{ fontSize: 10.5 }}>UMBRAL APROB.</div></div>
              <div><div className="mono" style={{ fontSize: 17, color: "var(--amber)" }}>85</div><div className="faint" style={{ fontSize: 10.5 }}>UMBRAL REVISIÓN</div></div>
            </div>
            <div className="faint" style={{ fontSize: 11, marginTop: 8 }}>
              Los umbrales se <b>auto-calibran</b> por template a partir de sus ejemplos. Estos son los globales por defecto.
            </div>
            {tSel && <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>Template elegido: {maturityLabel(tSel.maturity)} · {tSel.refs_count} ejemplos</div>}
          </div>
        </div>
      </div>
    );

  if (stage === "processing")
    return (
      <div className="card ct-fade" style={{ maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
        <div className="spinner" style={{ margin: "8px auto 14px" }} />
        <h3 style={{ margin: 0 }}>Validando documento…</h3>
        <p className="muted">{file?.name} · contra {tSel?.nombre}</p>
        <div className="bar" style={{ margin: "12px 0 18px" }}><i /></div>
        <div style={{ textAlign: "left", maxWidth: 360, margin: "0 auto" }}>
          {PASOS.map((p, i) => (
            <div key={i} className={`step ${i < step ? "done" : i === step ? "active" : ""}`}>
              <div className="dot">{i < step ? "✓" : i + 1}</div><span className={i <= step ? "" : "faint"}>{p}</span>
            </div>
          ))}
        </div>
      </div>
    );

  // result
  if (!res) return null;
  return (
    <div className="ct-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <ResultadoDetalle res={res} fileName={file?.name} />

      {/* Paso 2 en curso: el gate ya se ve; la revisión de contenido corre con progreso */}
      {revisando && (
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <div className="muted" style={{ fontSize: 12.5 }}>Revisando el contenido (todo el documento)… podés ir leyendo la admisión de arriba.</div>
        </div>
      )}
      {/* Revisión en modo manual: el toggle quedó off → ofrecer correrla a pedido */}
      {!revisando && !res.revision && res.veredicto === "valido" && (
        <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div className="muted" style={{ fontSize: 12.5 }}>El contenido aún no se revisó (revisión en modo manual).</div>
          <button className="btn btn-primary" style={{ padding: "5px 12px" }} onClick={revisarAhora}>Revisar contenido ahora</button>
        </div>
      )}

      {/* Footer: decisión + promoción */}
      <div className="card">
        {err && <div style={{ color: "var(--red-ink)", marginBottom: 10 }}>{err}</div>}
        {decision === null && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div className="muted" style={{ fontSize: 12.5 }}>Revisá la evidencia de arriba. La decisión final la tomás vos.</div>
            <div className="row-actions">
              <button className="btn btn-red-o" onClick={() => decidir("rejected")}><X size={15} /> Rechazar</button>
              <button className="btn btn-green" onClick={() => decidir("approved")}><Check size={15} /> Aprobar</button>
            </div>
          </div>
        )}
        {decision === "rejected" && (
          <div style={{ color: "var(--red-ink)" }}>✕ Documento rechazado · <button className="btn btn-ghost" style={{ padding: "2px 8px" }} onClick={() => setDecision(null)}>Deshacer</button></div>
        )}
        {decision === "approved" && !promoted && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ color: "var(--green-ink)" }}>✓ Aprobado manualmente</div>
            <div className="faint" style={{ fontSize: 12 }}>Promover este documento a referencia mejora la precisión del template (sube su madurez).</div>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={promote} onChange={(e) => setPromote(e.target.checked)} />
              Usar este documento para mejorar el template
            </label>
            <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} onClick={confirmarPromo}>
              {promote ? "Confirmar y promover" : "Confirmar sin promover"}
            </button>
          </div>
        )}
        {promoted && (
          <div style={{ color: "var(--green-ink)" }}>
            ✓ {promote ? `Agregado como referencia · el template ahora tiene ${promoted.refs_count} ejemplos (${maturityLabel(promoted.maturity)})` : "Confirmado sin promover"}
          </div>
        )}
      </div>
      <button className="btn btn-ghost" style={{ alignSelf: "flex-start" }} onClick={reiniciar}>← Validar otro documento</button>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type Historial as H, type Veredicto, type ValidarResp } from "../api/client";
import { VeredictoChip } from "../components/ui";
import { ResultadoDetalle } from "../components/ResultadoDetalle";
import { useActivity } from "../components/Activity";
import { errMsg, maturityLabel } from "../design/tokens";
import { Stat } from "../design/facets";
import { ArrowLeft, Check, X, Search } from "lucide-react";
import "./Templates.css";

const VER: { k: Veredicto; label: string; fg: string; bg: string; border: string; dot: string }[] = [
  { k: "valido",          label: "Válido",          fg: "#0d6b53", bg: "#e9f5f0", border: "#c3e7da", dot: "#12a87f" },
  { k: "revision_manual", label: "Revisión manual", fg: "#946312", bg: "#fdf6ea", border: "#f0ddb6", dot: "#e0a32e" },
  { k: "invalido",        label: "Inválido",        fg: "#b42318", bg: "#fef3f2", border: "#fecdc9", dot: "#d0473e" },
  { k: "faltan_datos",    label: "Faltan datos",    fg: "#5b6b78", bg: "#f4f6f8", border: "#dce3e8", dot: "#94a3b8" },
];

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
  const [q, setQ] = useState("");
  const [ver, setVer] = useState<Set<Veredicto>>(new Set());
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
  const s = q.trim().toLowerCase();
  const buscadas = h.items.filter((it) => !s || it.doc.toLowerCase().includes(s) || it.tipo_doc.toLowerCase().includes(s));
  const items = buscadas.filter((it) => ver.size === 0 || ver.has(it.veredicto));
  const COLS = "1.7fr 1.3fr 1.2fr 70px 1fr";
  return (
    <div className="ct-fade">
      {err && <div style={{ background: "#fef3f2", border: "1px solid #fecdc9", color: "#b42318", borderRadius: 10, padding: "10px 14px", marginBottom: 14, fontSize: 13 }}>{err}</div>}

      {/* Resumen */}
      <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
        <Stat value={m.validados} label="validados" title="Total de documentos validados (todo el historial)" />
        <Stat value={`${m.aprobacion_pct}%`} label="% de aprobación" color="#0d6b53" title="Proporción de validaciones aprobadas por un humano" />
        <Stat value={m.pendientes} label="pendientes de revisión" color={m.pendientes ? "#946312" : undefined} title="Casos admitidos sin decisión humana registrada" />
        <Stat value={m.promovidos} label="promovidos a referencia" color="#0e7c86" title="Documentos usados como ejemplo de calibración de su template" />
      </div>

      {/* Toolbar */}
      <div style={{ background: "#fff", border: "1px solid #e7edf0", borderRadius: 12, padding: "12px 16px", marginBottom: 16, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
          <Search size={14} color="#9aa7b0" style={{ position: "absolute", left: 9 }} />
          <input placeholder="Buscar documento o template…" value={q} onChange={(e) => setQ(e.target.value)} style={{ border: "1px solid #dce3e8", borderRadius: 8, padding: "7px 10px 7px 30px", fontSize: 12.5, width: 240, background: "#fafbfc", color: "#2b3a45" }} />
        </div>
        <span style={{ fontSize: 11.5, color: "#9aa7b0", fontWeight: 600, letterSpacing: .3 }}>VEREDICTO</span>
        {VER.map((v) => {
          const count = buscadas.filter((it) => it.veredicto === v.k).length;
          const op = ver.size === 0 || ver.has(v.k) ? 1 : .4;
          return (
            <button key={v.k} onClick={() => setVer((set) => { const n = new Set(set); n.has(v.k) ? n.delete(v.k) : n.add(v.k); return n; })}
              style={{ border: `1.5px solid ${v.border}`, background: v.bg, borderRadius: 20, padding: "4px 11px 4px 8px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, opacity: op, transition: "opacity .15s" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: v.dot }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: v.fg }}>{v.label}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: v.fg, background: "rgba(255,255,255,.65)", borderRadius: 9, padding: "0 6px" }}>{count}</span>
            </button>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: "#7e8f9a" }}><b style={{ color: "#2b3a45" }}>{items.length}</b> de {h.items.length}</span>
      </div>

      {/* Tabla */}
      <div style={{ background: "#fff", border: "1px solid #e4eaee", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 3px rgba(20,40,55,.05)" }}>
        <div style={{ display: "grid", gridTemplateColumns: COLS, padding: "11px 18px", background: "#f7f9fa", borderBottom: "1px solid #e7edf0", fontSize: 10.5, letterSpacing: .6, fontWeight: 700, color: "#90a0aa" }}>
          <div>DOCUMENTO</div><div>TEMPLATE</div><div>VEREDICTO</div><div style={{ textAlign: "center" }}>SCORE</div><div>FECHA</div>
        </div>
        {items.map((it) => (
          <div key={it.thread_id} className="tpl-leafrow" role="button" tabIndex={0} style={{ display: "grid", gridTemplateColumns: COLS, alignItems: "center", padding: "11px 18px", borderBottom: "1px solid #eef2f4", cursor: "pointer", animation: "czfade .2s ease" }}
            title="Ver el detalle del análisis"
            onClick={() => abrir(it.thread_id, it.doc, !!it.promovido_a_ref)} onKeyDown={(e) => { if (e.key === "Enter") abrir(it.thread_id, it.doc, !!it.promovido_a_ref); }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, paddingRight: 12 }}>
              <span style={{ fontFamily: "ui-monospace,Menlo,monospace", fontSize: 12, color: "#1c2c36", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.doc}</span>
              {!!it.promovido_a_ref && <span title="Promovido a referencia" style={{ fontSize: 10, color: "#0b6b74", background: "#eef7f8", border: "1px solid #bfe0e4", borderRadius: 5, padding: "0 6px", flex: "none" }}>↑ ref</span>}
            </span>
            <span style={{ fontSize: 12, color: "#52646f" }}>{it.tipo_doc}</span>
            <span><VeredictoChip v={it.veredicto} /></span>
            <span style={{ textAlign: "center", fontFamily: "ui-monospace,Menlo,monospace", fontSize: 12.5, fontWeight: 600, color: it.score != null ? "#2b3a45" : "#b6c0c7" }}>{it.score ?? "—"}</span>
            <span style={{ fontSize: 11.5, color: "#94a3ab" }}>{it.fecha}</span>
          </div>
        ))}
        {!items.length && (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "#8b9aa4" }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#5d7180" }}>{h.items.length ? "Sin resultados" : "Sin validaciones todavía"}</div>
            {h.items.length > 0 && <div style={{ fontSize: 12.5, marginTop: 5 }}>Ninguna coincide con los filtros.</div>}
          </div>
        )}
      </div>
    </div>
  );
}

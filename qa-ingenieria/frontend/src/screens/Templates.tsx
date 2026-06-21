import { useEffect, useState } from "react";
import { api, type Tipo, type Cobertura } from "../api/client";
import { MaturityBadge, Dropzone } from "../components/ui";
import { PreviewModal } from "../components/PreviewModal";
import { ZonaEditor } from "../components/ZonaEditor";
import { RequisitosEditor } from "../components/RequisitosEditor";
import { useActivity } from "../components/Activity";
import { errMsg } from "../design/tokens";
import { Plus, Trash2, ArrowLeft, Eye, Upload } from "lucide-react";

export function Templates() {
  const [tipos, setTipos] = useState<Tipo[]>([]);
  const [detail, setDetail] = useState<any | null>(null);
  const [showNew, setShowNew] = useState(false);

  const load = () => api.listTipos().then(setTipos).catch(() => {});
  useEffect(() => { load(); }, []);

  async function open(id: string) { setDetail(await api.getTipo(id)); }
  async function del(id: string) { await api.delTipo(id); load(); }

  if (detail) return <Detalle d={detail} onBack={() => { setDetail(null); load(); }} reload={() => open(detail.tipo_doc)} />;

  return (
    <div className="ct-fade">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={15} /> Nuevo template</button>
      </div>
      <div className="table">
        <div className="tr head" style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1.1fr 80px" }}>
          <span>TIPO DE DOCUMENTO</span><span>DISCIPLINAS</span><span>REFERENCIAS</span><span>MADUREZ</span><span>ACCIONES</span>
        </div>
        {tipos.map((t) => (
          <div key={t.tipo_doc} className="tr row" role="button" tabIndex={0} style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1.1fr 80px" }} onClick={() => open(t.tipo_doc)} onKeyDown={(e) => { if (e.key === "Enter") open(t.tipo_doc); }}>
            <span><b>{t.nombre}</b><div className="faint mono" style={{ fontSize: 11 }}>{t.tipo_doc}</div></span>
            <span className="muted">{(t.disciplinas || []).join(", ") || "—"}</span>
            <span className="mono">{t.refs_count} docs</span>
            <span><MaturityBadge m={t.maturity} /></span>
            <span><button className="btn btn-ghost" style={{ padding: "5px 8px" }} onClick={(e) => { e.stopPropagation(); del(t.tipo_doc); }}><Trash2 size={14} color="var(--red)" /></button></span>
          </div>
        ))}
        {!tipos.length && <div className="tr"><span className="faint">No hay templates. Creá el primero con “Nuevo template”.</span></div>}
      </div>
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

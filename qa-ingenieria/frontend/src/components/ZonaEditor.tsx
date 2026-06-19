import { useRef, useState } from "react";
import { api, type Zona, type BBox, type RuleTipo } from "../api/client";
import { errMsg } from "../design/tokens";
import { useActivity } from "./Activity";
import { Trash2, Wand2, Save, ChevronLeft, ChevronRight, Anchor, Copy } from "lucide-react";

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const round = (b: BBox): BBox => ({ x: +b.x.toFixed(4), y: +b.y.toFixed(4), w: +b.w.toFixed(4), h: +b.h.toFixed(4) });
const num = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : 0);

/** Normaliza una zona entrante: garantiza bbox válido (las zonas-regla del capturador
 *  pueden venir SIN coordenadas). Evita el crash al renderizar `z.bbox.x`. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normZona(z: any): Zona {
  const b = (z?.bbox || {}) as Partial<BBox>;
  return {
    ...(z as Zona),
    nombre: z?.nombre || "Zona",
    pagina: Number(z?.pagina) || 1,
    bbox: { x: num(b.x), y: num(b.y), w: num(b.w), h: num(b.h) },
  };
}

const PRESETS: { label: string; bbox: BBox }[] = [
  { label: "Encabezado", bbox: { x: 0, y: 0, w: 1, h: 0.18 } },
  { label: "Pie / rótulo", bbox: { x: 0, y: 0.82, w: 1, h: 0.18 } },
  { label: "Lateral derecho", bbox: { x: 0.72, y: 0, w: 0.28, h: 1 } },
  { label: "Página completa", bbox: { x: 0, y: 0, w: 1, h: 1 } },
];

type Drag = { mode: "draw" | "move" | "resize"; idx?: number; start: { x: number; y: number }; base?: BBox };
type RefItem = { ref_id: string; filename: string; paginas?: number };

export function ZonaEditor({ tipoDoc, referencias, zonasIniciales, onSaved }: {
  tipoDoc: string; referencias: RefItem[]; zonasIniciales: Zona[]; onSaved: (refs: number) => void;
}) {
  const refs = Array.isArray(referencias) ? referencias : [];
  const [zonas, setZonas] = useState<Zona[]>(() => (Array.isArray(zonasIniciales) ? zonasIniciales : []).map(normZona));
  const [refIdx, setRefIdx] = useState(0);
  const [page, setPage] = useState(1);
  const [draw, setDraw] = useState<BBox | null>(null);
  const [sel, setSel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const drag = useRef<Drag | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const refActual = refs[refIdx] || refs[0];
  const refId = refActual?.ref_id || null;
  const maxPages = Math.max(1, refActual?.paginas || 1);
  const { run } = useActivity();

  const rel = (e: React.MouseEvent) => {
    const r = boxRef.current!.getBoundingClientRect();
    return { x: clamp01((e.clientX - r.left) / r.width), y: clamp01((e.clientY - r.top) / r.height) };
  };

  function canvasDown(e: React.MouseEvent) {
    drag.current = { mode: "draw", start: rel(e) };
    setDraw({ ...drag.current.start, w: 0, h: 0 });
  }
  function zoneDown(e: React.MouseEvent, i: number) {
    e.stopPropagation(); setSel(i);
    drag.current = { mode: "move", idx: i, start: rel(e), base: { ...zonas[i].bbox } };
  }
  function handleDown(e: React.MouseEvent, i: number) {
    e.stopPropagation(); setSel(i);
    drag.current = { mode: "resize", idx: i, start: rel(e), base: { ...zonas[i].bbox } };
  }
  function onMove(e: React.MouseEvent) {
    const d = drag.current; if (!d) return;
    const p = rel(e);
    if (d.mode === "draw") {
      setDraw({ x: Math.min(d.start.x, p.x), y: Math.min(d.start.y, p.y), w: Math.abs(p.x - d.start.x), h: Math.abs(p.y - d.start.y) });
    } else if (d.mode === "move" && d.base) {
      const nx = clamp01(d.base.x + (p.x - d.start.x)), ny = clamp01(d.base.y + (p.y - d.start.y));
      update(d.idx!, { bbox: round({ x: Math.min(nx, 1 - d.base.w), y: Math.min(ny, 1 - d.base.h), w: d.base.w, h: d.base.h }) });
    } else if (d.mode === "resize" && d.base) {
      update(d.idx!, { bbox: round({ x: d.base.x, y: d.base.y, w: Math.max(0.02, clamp01(p.x) - d.base.x), h: Math.max(0.02, clamp01(p.y) - d.base.y) }) });
    }
  }
  function onUp() {
    const d = drag.current; drag.current = null;
    if (d?.mode === "draw" && draw && draw.w > 0.02 && draw.h > 0.02) {
      setZonas((zs) => [...zs, { nombre: `Zona ${zs.length + 1}`, pagina: page, bbox: round(draw), requerido: true }]);
      setSel(zonas.length);
    }
    setDraw(null);
  }

  const update = (i: number, patch: Partial<Zona>) => setZonas((zs) => zs.map((z, j) => (j === i ? { ...z, ...patch } : z)));
  const setIdentidad = (i: number) => setZonas((zs) => zs.map((z, j) => ({ ...z, identidad: j === i })));
  const del = (i: number) => setZonas((zs) => zs.filter((_, j) => j !== i));
  function dup(i: number) {
    setZonas((zs) => {
      const c: Zona = { ...zs[i], nombre: `${zs[i].nombre} (copia)`, identidad: false, bbox: { ...zs[i].bbox } };
      return [...zs.slice(0, i + 1), c, ...zs.slice(i + 1)];
    });
    setSel(i + 1);
  }
  const addPreset = (p: { label: string; bbox: BBox }) => { setZonas((zs) => [...zs, { nombre: p.label, pagina: page, bbox: p.bbox, requerido: true }]); setSel(zonas.length); };

  async function sugerir() {
    setBusy(true); setMsg("");
    try {
      const { zona } = await run("Sugerir zona de identidad", () => api.zonaSugerida(tipoDoc),
        ["Analizando la referencia…", "Ubicando el bloque de identidad…"]);
      setZonas((zs) => [{ nombre: "Identidad (sugerida)", pagina: 1, bbox: round(zona), identidad: true }, ...zs.filter((z) => !z.identidad)]);
      setSel(0); setPage(1);
    } catch (e) { setMsg("No se pudo sugerir: " + errMsg(e)); }
    finally { setBusy(false); }
  }
  async function guardar() {
    setBusy(true); setMsg("");
    try {
      const r = await run("Guardar zonas y recalibrar", () => api.putZonas(tipoDoc, zonas),
        ["Guardando zonas…", "Cargando modelo de embeddings…", "Re-embebiendo referencias…"]);
      setMsg(`Guardado ✓ · ${r.refs_reembebidas} referencias re-embebidas`); onSaved(r.refs_reembebidas);
    } catch (e) { setMsg("No se pudo guardar: " + errMsg(e)); }
    finally { setBusy(false); }
  }

  const url = refId ? api.refPreviewUrl(tipoDoc, refId, page) : null;
  const enPagina = (z: Zona) => (z.pagina || 1) === page;

  return (
    <div className="card">
      <div className="dim-h">Zonas de la página <span className="faint" style={{ fontWeight: 400, fontSize: 11.5 }}>· dónde buscar lo importante</span></div>
      <div className="faint" style={{ fontSize: 11.5, marginBottom: 10, lineHeight: 1.6 }}>
        Dibujá una zona arrastrando (o un preset); clic en una zona para <b>moverla</b> o
        <b> redimensionarla</b> (puntito ◢). Una zona <b>identidad</b> alimenta el parecido visual.
        Una zona con <b>campo</b> extrae un valor para validarlo:
        <br />· con <b>recuadro</b> (sin ancla) → el valor se busca <b>dentro del recuadro</b> (posición fija).
        <br />· con <b>ancla</b> (etiqueta/regex, ej. <span className="mono">Código:</span>) → el valor se busca
        <b> junto al ancla</b>, dondequiera que esté (posición <b>variable</b>).
      </div>

      <div style={{ display: "grid", gridTemplateColumns: url ? "minmax(280px, 440px) 1fr" : "1fr", gap: 16, alignItems: "start" }}>
        {url && (
          <div>
            {refs.length > 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12 }}>
                <span className="faint" style={{ whiteSpace: "nowrap" }}>Referencia:</span>
                <select className="select" style={{ padding: "4px 8px", flex: 1 }} value={refIdx}
                  onChange={(e) => { setRefIdx(Number(e.target.value)); setPage(1); }}>
                  {refs.map((r, i) => <option key={r.ref_id} value={i}>{r.filename}</option>)}
                </select>
              </div>
            )}
            {maxPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 6 }}>
                <button className="btn btn-ghost" style={{ padding: "3px 7px" }} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={14} /></button>
                <span className="mono" style={{ fontSize: 12 }}>Página {page} / {maxPages}</span>
                <button className="btn btn-ghost" style={{ padding: "3px 7px" }} disabled={page >= maxPages} onClick={() => setPage((p) => p + 1)}><ChevronRight size={14} /></button>
              </div>
            )}
            <div ref={boxRef} onMouseDown={canvasDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
              style={{ position: "relative", border: "1px solid var(--border2)", borderRadius: 8, overflow: "hidden", cursor: "crosshair", userSelect: "none", background: "#F4F7F7" }}>
              <img src={url} alt="referencia" draggable={false} style={{ width: "100%", display: "block" }} />
              {zonas.map((z, i) => enPagina(z) && z.bbox.w > 0 && z.bbox.h > 0 && (
                <div key={i} onMouseDown={(e) => zoneDown(e, i)} title={z.nombre}
                  style={{
                    position: "absolute", left: `${z.bbox.x * 100}%`, top: `${z.bbox.y * 100}%`,
                    width: `${z.bbox.w * 100}%`, height: `${z.bbox.h * 100}%`, cursor: "move",
                    border: `2px ${z.identidad ? "solid var(--teal)" : "dashed var(--amber)"}`,
                    background: z.identidad ? "rgba(14,110,120,.08)" : "rgba(194,134,14,.08)",
                    boxShadow: i === sel ? "0 0 0 2px rgba(14,110,120,.35)" : "none",
                  }}>
                  <span style={{ position: "absolute", top: -15, left: 0, fontSize: 9.5, fontFamily: "var(--mono)", color: z.identidad ? "var(--teal)" : "var(--amber-ink)", whiteSpace: "nowrap" }}>
                    {z.nombre}{z.ancla_inicio || z.ancla_fin ? " ⚓" : ""}
                  </span>
                  <div onMouseDown={(e) => handleDown(e, i)} style={{ position: "absolute", right: -5, bottom: -5, width: 11, height: 11, background: "var(--teal)", borderRadius: 2, cursor: "nwse-resize" }} />
                </div>
              ))}
              {draw && <div style={{ position: "absolute", left: `${draw.x * 100}%`, top: `${draw.y * 100}%`, width: `${draw.w * 100}%`, height: `${draw.h * 100}%`, border: "2px solid var(--teal)", background: "rgba(14,110,120,.12)" }} />}
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {PRESETS.map((p) => <button key={p.label} className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: 11 }} onClick={() => addPreset(p)}>+ {p.label}</button>)}
            </div>
          </div>
        )}

        <div>
          {!url && <div className="faint" style={{ fontSize: 12, marginBottom: 8 }}>Subí una referencia para dibujar zonas sobre el documento. Mientras, presets:</div>}
          {!url && <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>{PRESETS.map((p) => <button key={p.label} className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: 11 }} onClick={() => addPreset(p)}>+ {p.label}</button>)}</div>}
          {zonas.length === 0 && <div className="faint" style={{ fontSize: 12 }}>Sin zonas. Dibujá una o agregá un preset.</div>}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {zonas.map((z, i) => (
              <div key={i} onClick={() => { setSel(i); if ((z.pagina || 1) !== page) setPage(z.pagina || 1); }}
                style={{ border: `1px solid ${i === sel ? "var(--teal)" : "var(--border2)"}`, borderRadius: 8, padding: 8, fontSize: 12 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input className="input" style={{ padding: "4px 7px", flex: 1 }} value={z.nombre} onChange={(e) => update(i, { nombre: e.target.value })} />
                  <label className="faint" style={{ display: "flex", gap: 3, alignItems: "center", fontSize: 11, whiteSpace: "nowrap" }} title="Página del documento">
                    pág
                    <input type="number" min={1} className="input mono" style={{ padding: "4px 4px", width: 44 }}
                      value={z.pagina || 1} onClick={(e) => e.stopPropagation()}
                      onChange={(e) => update(i, { pagina: Math.max(1, parseInt(e.target.value, 10) || 1) })} />
                  </label>
                  <label style={{ display: "flex", gap: 4, alignItems: "center", whiteSpace: "nowrap" }} title="Usar para el parecido visual">
                    <input type="radio" checked={!!z.identidad} onChange={() => setIdentidad(i)} /> ident.
                  </label>
                  <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Duplicar bloque" onClick={(e) => { e.stopPropagation(); dup(i); }}><Copy size={13} /></button>
                  <button className="btn btn-ghost" style={{ padding: "3px 6px" }} title="Borrar bloque" onClick={(e) => { e.stopPropagation(); del(i); }}><Trash2 size={13} color="var(--red)" /></button>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 6 }}>
                  <select className="select" style={{ padding: "4px 7px", width: 88 }} value={z.comparar || "texto"} onChange={(e) => update(i, { comparar: e.target.value as "texto" | "visual" })} title="texto: extrae y valida un valor · visual: compara la imagen del recuadro">
                    <option value="texto">texto</option>
                    <option value="visual">visual</option>
                  </select>
                  {z.comparar === "visual" ? (
                    <span className="faint" style={{ fontSize: 11 }}>se compara por imagen (recorte + embeddings); no extrae texto</span>
                  ) : (
                    <>
                      <input className="input" style={{ padding: "4px 7px", width: 100 }} placeholder="campo" value={z.campo || ""} onChange={(e) => update(i, { campo: e.target.value })} />
                      <select className="select" style={{ padding: "4px 7px", width: 96 }} value={z.tipo || "regex"} onChange={(e) => update(i, { tipo: e.target.value as RuleTipo })}>
                        <option value="regex">regex</option>
                        <option value="filename">= filename</option>
                        <option value="presencia">presencia</option>
                      </select>
                      {(z.tipo || "regex") !== "presencia" && <input className="input mono" style={{ padding: "4px 7px", flex: 1, fontSize: 11 }} placeholder={z.tipo === "filename" ? "patrón opcional: clave" : "patrón regex"} value={z.patron || ""} onChange={(e) => update(i, { patron: e.target.value })} />}
                      {z.campo && <label style={{ display: "flex", gap: 4, alignItems: "center", whiteSpace: "nowrap" }}><input type="checkbox" checked={z.requerido !== false} onChange={(e) => update(i, { requerido: e.target.checked })} /> req</label>}
                    </>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 6 }} title="Ancla de texto (regex). El valor se busca junto al ancla → la zona sigue al contenido (posición variable). Si no hay ancla, se usa el recuadro.">
                  <Anchor size={12} color="var(--faint)" />
                  <input className="input mono" style={{ padding: "4px 7px", flex: 1, fontSize: 11 }} placeholder="ancla: etiqueta antes del valor (ej. Código:)" value={z.ancla_inicio || ""} onChange={(e) => update(i, { ancla_inicio: e.target.value })} />
                  <input className="input mono" style={{ padding: "4px 7px", flex: 1, fontSize: 11 }} placeholder="ancla fin (opcional, para banda)" value={z.ancla_fin || ""} onChange={(e) => update(i, { ancla_fin: e.target.value })} />
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
            <button className="btn btn-ghost" disabled={busy || !refId} onClick={sugerir} title={refId ? "" : "necesita una referencia"}><Wand2 size={14} /> Sugerir identidad</button>
            <button className="btn btn-primary" disabled={busy} onClick={guardar}><Save size={14} /> {busy ? "Guardando…" : "Guardar zonas"}</button>
            {msg && <span className={msg.startsWith("No se pudo") ? "" : "muted"} style={msg.startsWith("No se pudo") ? { color: "var(--red-ink)" } : undefined}>{msg}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

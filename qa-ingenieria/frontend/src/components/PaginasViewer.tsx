import { useState } from "react";
import { ChevronLeft, ChevronRight, ZoomIn } from "lucide-react";
import { api, type BBox, type CheckState, type ZonaResultado } from "../api/client";
import { C } from "../design/tokens";

const COLOR: Record<CheckState, { b: string; bg: string; ink: string }> = {
  pass: { b: C.green, bg: "rgba(31,138,91,.14)", ink: C.greenInk },
  fail: { b: C.red, bg: "rgba(192,65,59,.16)", ink: C.redInk },
  warn: { b: C.amber, bg: "rgba(194,134,14,.16)", ink: C.amberInk },
  info: { b: C.teal, bg: "rgba(14,110,120,.10)", ink: C.teal },
};
const GLYPH: Record<CheckState, string> = { pass: "✓", fail: "✕", warn: "!", info: "i" };
const ESTADO_LABEL: Record<CheckState, string> = { pass: "cumple", fail: "no cumple", warn: "a revisar", info: "informativo" };

function ZonaBox({ z }: { z: ZonaResultado }) {
  if (!z.bbox) return null;
  const c = COLOR[z.estado];
  const b: BBox = z.bbox;
  const tag = z.score != null ? `${z.nombre} · ${Math.round(z.score)}%` : z.nombre;
  return (
    <div
      title={`${z.nombre} — ${ESTADO_LABEL[z.estado]}${z.detalle ? ` · ${z.detalle}` : ""}`}
      style={{
        position: "absolute", left: `${b.x * 100}%`, top: `${b.y * 100}%`,
        width: `${b.w * 100}%`, height: `${b.h * 100}%`,
        border: `2px solid ${c.b}`, background: c.bg, borderRadius: 4, boxSizing: "border-box",
      }}
    >
      <span style={{
        position: "absolute", top: -10, left: -2, background: c.b, color: "#fff",
        fontSize: 9.5, fontWeight: 700, padding: "1px 5px", borderRadius: 4, whiteSpace: "nowrap",
        maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.5,
      }}>{GLYPH[z.estado]} {tag}</span>
    </div>
  );
}

/** Visor multipágina del documento validado con las zonas dibujadas encima, coloreadas por estado
 *  (cumple/no cumple/a revisar/informativo). Cumple OBSERVABILIDAD: se ve DÓNDE valida y dónde no.
 *  Las páginas se piden ON-DEMAND al endpoint del caso (no viajan en el payload): si hay `threadId`
 *  + `nPaginas` cubre TODO el documento; si no, cae a las `imagenes` pre-renderizadas. */
export function PaginasViewer({ threadId, nPaginas, imagenes, zonas, cajetinBbox }: {
  threadId?: string; nPaginas?: number; imagenes?: string[]; zonas: ZonaResultado[]; cajetinBbox?: BBox | null;
}) {
  const [pg, setPg] = useState(0);
  const [zoom, setZoom] = useState(false);
  const n = nPaginas || imagenes?.length || 0;
  const page = Math.min(pg, Math.max(0, n - 1));
  const src = (i: number): string | null =>
    threadId ? api.casoPaginaUrl(threadId, i + 1) : (imagenes?.[i] ?? null);
  const img = n ? src(page) : null;
  const zonasPg = (zonas || []).filter((z) => (z.pagina || 1) === page + 1 && z.bbox);
  const conZona = new Set((zonas || []).filter((z) => z.bbox).map((z) => (z.pagina || 1) - 1));
  const estadosPresentes = Array.from(new Set((zonas || []).map((z) => z.estado)));

  const lienzo = (
    <div style={{ position: "relative", display: "inline-block", width: "100%", background: "#fff" }}>
      {img
        ? <img src={img} alt={`Página ${page + 1}`} style={{ width: "100%", display: "block", objectFit: "contain" }} />
        : <div className="faint" style={{ padding: 24, textAlign: "center" }}>Sin previsualización</div>}
      {zonasPg.map((z, i) => <ZonaBox key={i} z={z} />)}
      {/* Fallback: si no hay zonas en esta página pero sí el cajetín detectado por visión */}
      {!zonasPg.length && cajetinBbox && page === 0 && (
        <div className="cajetin-box" style={{ left: `${cajetinBbox.x * 100}%`, top: `${cajetinBbox.y * 100}%`, width: `${cajetinBbox.w * 100}%`, height: `${cajetinBbox.h * 100}%` }}>
          <span className="lab">Cajetín detectado</span>
        </div>
      )}
    </div>
  );

  return (
    <div className="card" style={{ padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div className="eyebrow" style={{ margin: 0 }}>PÁGINAS Y ZONAS</div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          {n > 1 && (
            <>
              <button className="btn btn-ghost" style={{ padding: "2px 6px" }} disabled={page === 0} onClick={() => setPg(page - 1)}><ChevronLeft size={14} /></button>
              <span className="mono faint" style={{ fontSize: 11.5 }}>pág {page + 1}/{n}</span>
              <button className="btn btn-ghost" style={{ padding: "2px 6px" }} disabled={page >= n - 1} onClick={() => setPg(page + 1)}><ChevronRight size={14} /></button>
            </>
          )}
          {img && <button className="btn btn-ghost" style={{ padding: "2px 7px", display: "flex", gap: 4, alignItems: "center" }} onClick={() => setZoom(true)}><ZoomIn size={13} /> ampliar</button>}
        </div>
      </div>

      <div style={{ cursor: img ? "zoom-in" : "default", border: "1px solid var(--border2)", borderRadius: 6, overflow: "hidden" }} onClick={() => img && setZoom(true)}>
        {lienzo}
      </div>

      {/* Miniaturas-índice: qué páginas tienen zonas */}
      {n > 1 && (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 8 }}>
          {Array.from({ length: n }, (_, i) => (
            <button key={i} onClick={() => setPg(i)} title={conZona.has(i) ? "tiene zonas" : "sin zonas"}
              style={{
                width: 26, height: 22, fontSize: 10.5, borderRadius: 4, cursor: "pointer",
                border: `1px solid ${i === page ? C.teal : "var(--border)"}`,
                background: i === page ? C.teal50 : "#fff", color: C.ink, fontWeight: i === page ? 700 : 400,
                position: "relative",
              }}>
              {i + 1}
              {conZona.has(i) && <span style={{ position: "absolute", top: 2, right: 2, width: 5, height: 5, borderRadius: "50%", background: C.teal }} />}
            </button>
          ))}
        </div>
      )}

      {estadosPresentes.length > 0 && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, fontSize: 11 }}>
          {(["pass", "warn", "fail", "info"] as CheckState[]).filter((e) => estadosPresentes.includes(e)).map((e) => (
            <span key={e} style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--muted)" }}>
              <span style={{ width: 11, height: 11, borderRadius: 3, border: `2px solid ${COLOR[e].b}`, background: COLOR[e].bg }} />
              {ESTADO_LABEL[e]}
            </span>
          ))}
        </div>
      )}

      {zoom && img && (
        <div className="overlay" onClick={() => setZoom(false)} style={{ alignItems: "center", justifyContent: "center" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 12, width: 900, maxWidth: "94vw", maxHeight: "92vh", display: "flex", flexDirection: "column", boxShadow: "0 24px 60px rgba(0,0,0,.32)" }}>
            <div className="modal-h">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <b style={{ fontSize: 13 }}>Página {page + 1} de {n}</b>
                {n > 1 && (
                  <>
                    <button className="btn btn-ghost" style={{ padding: "2px 6px" }} disabled={page === 0} onClick={() => setPg(page - 1)}><ChevronLeft size={14} /></button>
                    <button className="btn btn-ghost" style={{ padding: "2px 6px" }} disabled={page >= n - 1} onClick={() => setPg(page + 1)}><ChevronRight size={14} /></button>
                  </>
                )}
              </div>
              <button className="btn btn-ghost" onClick={() => setZoom(false)}>✕</button>
            </div>
            <div style={{ padding: 18, overflow: "auto", background: "var(--bg)", display: "flex", justifyContent: "center" }}>
              <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
                <img src={img} alt={`Página ${page + 1}`} style={{ maxWidth: "100%", maxHeight: "78vh", display: "block", borderRadius: 6, border: "1px solid var(--border2)", background: "#fff" }} />
                {zonasPg.map((z, i) => <ZonaBox key={i} z={z} />)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

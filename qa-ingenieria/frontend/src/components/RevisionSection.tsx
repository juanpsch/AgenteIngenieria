import { useMemo, useState } from "react";
import { api, type EstadoRevision, type Hallazgo, type RevisionBlock, type Severidad, type ZonaResultado, type CheckState } from "../api/client";
import { PaginasViewer } from "./PaginasViewer";
import { useActivity } from "./Activity";
import { errMsg } from "../design/tokens";

const VERDICTO: Record<string, { label: string; cls: string; glyph: string }> = {
  aprobado: { label: "APROBADO", cls: "v-ok", glyph: "✓" },
  aprobado_con_notas: { label: "APROBADO CON NOTAS", cls: "v-ok", glyph: "✓" },
  observado: { label: "OBSERVADO", cls: "v-amber", glyph: "!" },
  rechazado: { label: "RECHAZADO", cls: "v-red", glyph: "✕" },
  pendiente_senior: { label: "PENDIENTE SENIOR", cls: "v-info", glyph: "↑" },
};
const SEV_CLS: Record<Severidad, string> = { bloqueante: "mat-red", mayor: "mat-amber", menor: "mat-neutral", observacion: "mat-ok" };
const EST_BADGE: Record<EstadoRevision, string> = { ok: "b-pass", fallo: "b-fail", advertencia: "b-warn", no_verificable: "b-info" };
const EST_GLYPH: Record<EstadoRevision, string> = { ok: "✓", fallo: "✕", advertencia: "!", no_verificable: "?" };
const EST_OVL: Record<EstadoRevision, CheckState> = { ok: "pass", fallo: "fail", advertencia: "warn", no_verificable: "info" };
const DIM_LABEL: Record<string, string> = { legibilidad: "Legibilidad", norma: "Norma / nomenclatura", contenido: "Contenido", consistencia: "Consistencia" };

/** Sección "Revisión de contenido" (Fase 1): banner del veredicto de revisión + hallazgos agrupados
 *  por dimensión + overlay "ver en plano" + acciones para resolver el veredicto humano. */
export function RevisionSection({ rev, imagenes, threadId }: { rev: RevisionBlock; imagenes: string[]; threadId?: string }) {
  const { run } = useActivity();
  const [resuelto, setResuelto] = useState<string | null>(rev.resuelta ? rev.verdicto : null);
  const [notas, setNotas] = useState("");
  const [err, setErr] = useState("");

  const v = VERDICTO[rev.verdicto || ""] || VERDICTO.observado;
  const porDim = useMemo(() => {
    const m: Record<string, Hallazgo[]> = {};
    for (const h of rev.hallazgos || []) (m[h.dimension] ||= []).push(h);
    return m;
  }, [rev.hallazgos]);
  const overlays: ZonaResultado[] = (rev.hallazgos || [])
    .filter((h) => h.ubicacion?.bbox)
    .map((h) => ({ nombre: h.check_id, pagina: h.ubicacion!.pagina, bbox: h.ubicacion!.bbox!, clase: "regla", estado: EST_OVL[h.estado], detalle: h.evidencia }));

  async function resolver(decision: "aprobado" | "aprobado_con_notas" | "observado" | "rechazado" | "escalar_senior") {
    if (!threadId) return;
    setErr("");
    try {
      const r = await run(`Resolver revisión: ${decision}`, () => api.revisionDecision(threadId, decision, notas || undefined));
      setResuelto(r.verdicto);
    } catch (e) { setErr(errMsg(e)); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="eyebrow" style={{ marginTop: 6 }}>REVISIÓN DE CONTENIDO (FASE 1)</div>

      <div className={`verdict ${v.cls}`} style={{ padding: "12px 16px" }}>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <div className="glyph">{v.glyph}</div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: ".6px" }}>VEREDICTO DE REVISIÓN</div>
            <div className="label">{v.label}</div>
            <div className="resumen">
              {rev.severidad_max ? `Severidad máxima: ${rev.severidad_max}. ` : "Sin hallazgos accionables. "}
              {rev.confiabilidad === "parcial" && "Confiabilidad parcial (hay checks no verificables)."}
            </div>
          </div>
        </div>
        {resuelto && <span className="chip mat-ok" style={{ alignSelf: "flex-start" }}>resuelto: {resuelto}</span>}
      </div>

      {Object.keys(porDim).map((dim) => (
        <div key={dim} className="card">
          <div className="dim-h">{DIM_LABEL[dim] || dim}</div>
          {porDim[dim].map((h, i) => (
            <div key={i} className="check" style={{ borderTop: i ? "1px solid var(--line)" : undefined, paddingTop: i ? 8 : 0 }}>
              <div className={`badge ${EST_BADGE[h.estado]}`} title={h.estado}>{EST_GLYPH[h.estado]}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="lab" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span>{h.check_id}</span>
                  <span className={`chip ${SEV_CLS[h.severidad]}`} style={{ fontSize: 9.5 }}>{h.severidad}</span>
                  {h.estado === "no_verificable" && <span className="chip mat-neutral" style={{ fontSize: 9.5 }}>no verificable</span>}
                  <span className="faint" style={{ fontSize: 10, fontWeight: 400 }}>{h.fuente}</span>
                  {h.ubicacion?.pagina && <span className="faint" style={{ fontSize: 10, fontWeight: 400 }}>pág {h.ubicacion.pagina}</span>}
                </div>
                {h.evidencia && <div className="det">{h.evidencia}</div>}
                <div className="det faint">{h.razonamiento}</div>
                {h.sugerencia && <div className="det" style={{ color: "var(--teal)" }}>→ {h.sugerencia}</div>}
              </div>
            </div>
          ))}
        </div>
      ))}

      {overlays.length > 0 && (
        <>
          <div className="faint" style={{ fontSize: 11.5 }}>Ubicación de los hallazgos en el plano:</div>
          <PaginasViewer imagenes={imagenes} zonas={overlays} />
        </>
      )}

      {threadId && !resuelto && (
        <div className="card">
          <div className="dim-h">Resolver revisión</div>
          <textarea value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Notas (opcional)…"
            style={{ width: "100%", minHeight: 48, fontSize: 12.5, padding: 8, borderRadius: 6, border: "1px solid var(--border)", resize: "vertical", boxSizing: "border-box" }} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
            <button className="btn btn-primary" style={{ padding: "5px 11px" }} onClick={() => resolver("aprobado")}>Aprobar</button>
            <button className="btn btn-ghost" style={{ padding: "5px 11px" }} onClick={() => resolver("aprobado_con_notas")}>Aprobar con notas</button>
            <button className="btn btn-ghost" style={{ padding: "5px 11px" }} onClick={() => resolver("observado")}>Enviar a corrección</button>
            <button className="btn btn-ghost" style={{ padding: "5px 11px" }} onClick={() => resolver("rechazado")}>Rechazar</button>
            <button className="btn btn-ghost" style={{ padding: "5px 11px", marginLeft: "auto" }} onClick={() => resolver("escalar_senior")}>Escalar a senior</button>
          </div>
          {err && <div style={{ color: "var(--red-ink)", marginTop: 6 }}>{err}</div>}
        </div>
      )}
    </div>
  );
}

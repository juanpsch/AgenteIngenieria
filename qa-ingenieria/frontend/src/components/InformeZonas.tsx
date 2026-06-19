import type { CheckState, ZonaResultado } from "../api/client";

const BADGE: Record<CheckState, string> = { pass: "b-pass", fail: "b-fail", warn: "b-warn", info: "b-info" };
const GLYPH: Record<CheckState, string> = { pass: "✓", fail: "✕", warn: "!", info: "i" };
const ESTADO_LABEL: Record<CheckState, string> = { pass: "cumple", fail: "no cumple", warn: "a revisar", info: "informativo" };
const CLASE_LABEL: Record<string, string> = { identidad: "identidad", visual: "visual", regla: "regla" };
const ORDEN: Record<CheckState, number> = { fail: 0, warn: 1, info: 2, pass: 3 };

/** Informe prolijo POR ZONA: qué reglas/zonas cumplen y cuáles no, con su ubicación (página) y,
 *  si son visuales, su parecido. Los problemas (no cumple / a revisar) van primero. */
export function InformeZonas({ zonas }: { zonas: ZonaResultado[] }) {
  if (!zonas?.length) return null;
  const orden = [...zonas].sort((a, b) => (ORDEN[a.estado] - ORDEN[b.estado]) || a.pagina - b.pagina);
  const cuenta = (e: CheckState) => zonas.filter((z) => z.estado === e).length;

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div className="dim-h" style={{ margin: 0 }}>Informe por zona</div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, fontSize: 11 }}>
          {(["pass", "warn", "fail"] as CheckState[]).map((e) =>
            cuenta(e) ? <span key={e} className={`chip ${e === "pass" ? "mat-ok" : e === "warn" ? "mat-amber" : "mat-red"}`}>{cuenta(e)} {ESTADO_LABEL[e]}</span> : null,
          )}
        </div>
      </div>
      <div className="faint" style={{ fontSize: 11.5, margin: "2px 0 8px" }}>
        Cada zona del template, evaluada por separado en este documento. Las visuales muestran su % de parecido.
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {orden.map((z, i) => (
          <div key={i} className="check" style={{ borderTop: i ? "1px solid var(--line)" : undefined, paddingTop: i ? 8 : 0 }}>
            <div className={`badge ${BADGE[z.estado]}`} role="img" aria-label={ESTADO_LABEL[z.estado]} title={ESTADO_LABEL[z.estado]}>{GLYPH[z.estado]}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="lab" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span>{z.nombre}</span>
                <span className="chip mat-neutral" style={{ fontSize: 9.5 }}>{CLASE_LABEL[z.clase] || z.clase}</span>
                {z.requerido && <span className="chip mat-amber" style={{ fontSize: 9.5 }}>requerido</span>}
                <span className="faint" style={{ fontSize: 10.5, fontWeight: 400 }}>pág {z.pagina}</span>
                {z.score != null && <span className="mono faint" style={{ fontSize: 10.5 }}>{Math.round(z.score)}%</span>}
              </div>
              {z.detalle && <div className="det">{z.detalle}</div>}
              {z.valor && <div className="det mono">«{z.valor}»</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

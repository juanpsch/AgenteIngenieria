import type { ScoreDetalle } from "../api/client";

const clamp = (x: number) => Math.max(0, Math.min(100, x));

function Componente({ label, val, peso }: { label: string; val: number; peso: number }) {
  return (
    <div style={{ border: "1px solid var(--border2)", borderRadius: 9, padding: "7px 11px", minWidth: 132 }}>
      <div style={{ fontSize: 11, color: "var(--muted)" }}>{label}</div>
      <div>
        <span className="mono" style={{ fontSize: 17, fontWeight: 600 }}>{val}%</span>
        <span className="faint" style={{ fontSize: 10.5 }}> · peso {peso}</span>
      </div>
    </div>
  );
}

export function ScoreBreakdown({ d }: { d: ScoreDetalle | null }) {
  if (!d || d.score == null) {
    return (
      <div className="card">
        <div className="dim-h">Similitud visual con el template</div>
        <div className="faint" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
          El template todavía no está calibrado (o no hay backend de embeddings activo): el score de
          similitud <b>no se calcula</b>. El veredicto se decide por <b>identidad</b> (¿es el tipo?) y
          <b> reglas</b> del rótulo. Sumá ejemplos de referencia para activar el score visual.
        </div>
      </div>
    );
  }

  const { score, cajetin, pagina, peso_cajetin, peso_pagina, n_referencias, ref_top, decisivo } = d;
  const appr = d.umbral_aprobacion;
  const rev = d.umbral_revision;
  const band = score >= appr ? "valido" : score >= rev ? "revision" : "invalido";
  const bandColor = band === "valido" ? "var(--green)" : band === "revision" ? "var(--amber)" : "var(--red)";
  const bandLabel = band === "valido" ? "sobre el umbral de aprobación" : band === "revision" ? "en zona de revisión" : "bajo el umbral de revisión";

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div className="dim-h" style={{ margin: 0 }}>Similitud visual con el template</div>
        <div className="mono" style={{ fontSize: 24, fontWeight: 600, color: bandColor }}>{score}%</div>
      </div>
      <div style={{ fontSize: 11.5, color: bandColor, marginBottom: 12 }}>
        {bandLabel} · {decisivo ? "decisivo (template calibrado)" : "informativo — todavía no decide (calibrando)"}
        {" · "}<span className="faint">{d.umbrales_auto ? "umbrales auto-calibrados del template" : "umbrales globales"}</span>
      </div>

      {/* Escala 0–100 con las tres bandas + umbrales + marcador del score */}
      <div style={{ position: "relative", marginTop: 22, marginBottom: 26 }}>
        <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden" }}>
          <div style={{ width: `${rev}%`, background: "var(--red-bg)" }} title="inválido" />
          <div style={{ width: `${appr - rev}%`, background: "var(--amber-bg)" }} title="revisión manual" />
          <div style={{ width: `${100 - appr}%`, background: "var(--green-bg)" }} title="válido" />
        </div>
        {/* marcador del score */}
        <div style={{ position: "absolute", left: `${clamp(score)}%`, top: -7, transform: "translateX(-50%)", textAlign: "center" }}>
          <div className="mono" style={{ fontSize: 10, color: bandColor, fontWeight: 600, marginBottom: 1 }}>▼</div>
        </div>
        {/* umbrales */}
        <div className="mono" style={{ position: "absolute", left: `${rev}%`, top: 18, transform: "translateX(-50%)", fontSize: 10, color: "var(--amber-ink)" }}>{rev}</div>
        <div className="mono" style={{ position: "absolute", left: `${appr}%`, top: 18, transform: "translateX(-50%)", fontSize: 10, color: "var(--green-ink)" }}>{appr}</div>
      </div>

      {/* Componentes ponderados */}
      <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
        {cajetin != null && <Componente label="Zona de identidad" val={cajetin} peso={peso_cajetin} />}
        {pagina != null && <Componente label="Página completa" val={pagina} peso={peso_pagina} />}
      </div>

      <div className="faint" style={{ fontSize: 11.5, marginTop: 11 }}>
        Comparado contra <b>{n_referencias}</b> ejemplo{n_referencias === 1 ? "" : "s"} de referencia
        {d.heredado_de && <> · <b>heredados de {d.heredado_de}</b> (todavía sin ejemplos propios)</>}
        {ref_top?.filename && (
          <> · más parecido: <span className="mono">{ref_top.filename}</span>{ref_top.score != null && <> ({ref_top.score}%)</>}</>
        )}
        {!!d.n_negativos && <> · {d.n_negativos} contra-ejemplo{d.n_negativos === 1 ? "" : "s"} (rechazados)</>}
      </div>
      {d.negativos != null && d.score_positivos != null && d.score_positivos > score && (
        <div style={{ fontSize: 11.5, marginTop: 4, color: "var(--red-ink)" }}>
          ⚠ Penalizado: se parece a un documento rechazado ({d.negativos}%) más que a los aprobados
          ({d.score_positivos}%) → score bajado de {d.score_positivos}% a {score}%.
        </div>
      )}
    </div>
  );
}

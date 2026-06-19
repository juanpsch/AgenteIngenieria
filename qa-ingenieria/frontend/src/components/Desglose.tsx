import { useState, type ReactNode } from "react";
import type { Check } from "../api/client";
import { CheckRow } from "./ui";

function dimPasa(checks: Check[]) {
  return !checks.some((c) => c.state === "fail" && c.requerido);
}

const SUB: Record<string, string> = {
  identidad: "¿El documento ES el tipo elegido? (empresa · tipo · rótulo · parecido visual)",
  completitud: "¿Están los campos del rótulo y las secciones obligatorias?",
};

function Rows({ checks, prefix }: { checks: Check[]; prefix: string }) {
  return checks.length
    ? <>{checks.map((c) => <CheckRow key={`${prefix}-${c.label}`} c={c} />)}</>
    : <div className="faint">—</div>;
}

export function Desglose({ ident, compl, preview }: { ident: Check[]; compl: Check[]; preview: ReactNode }) {
  const [layout, setLayout] = useState<"A" | "B" | "C">("A");

  const seg = (
    <div className="seg" style={{ marginLeft: "auto" }}>
      {(["A", "B", "C"] as const).map((k) => (
        <button key={k} className={layout === k ? "on" : ""} onClick={() => setLayout(k)}>
          {k === "A" ? "Dividida" : k === "B" ? "Tarjetas" : "Compacta"}
        </button>
      ))}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <div className="eyebrow">DESGLOSE POR DIMENSIÓN</div>
        {seg}
      </div>

      {layout === "A" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.25fr", gap: 18, alignItems: "start" }}>
          {preview}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {(["identidad", "completitud"] as const).map((dim) => (
              <div key={dim} className="card">
                <div className="dim-h">{dim === "identidad" ? "Identidad / pertenencia" : "Completitud / conformidad"}</div>
                <div className="faint" style={{ fontSize: 11.5, marginTop: -2, marginBottom: 6 }}>{SUB[dim]}</div>
                <Rows checks={dim === "identidad" ? ident : compl} prefix={dim} />
              </div>
            ))}
          </div>
        </div>
      )}

      {layout === "B" && (
        <>
          {preview}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
            {(["identidad", "completitud"] as const).map((dim) => {
              const checks = dim === "identidad" ? ident : compl;
              const pasa = dimPasa(checks);
              return (
                <div key={dim} className="card" style={{ borderLeft: `3px solid ${pasa ? "var(--green)" : "var(--amber)"}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div className="dim-h" style={{ margin: 0 }}>{dim === "identidad" ? "Identidad" : "Completitud"}</div>
                    <span className={`chip ${pasa ? "mat-ok" : "mat-amber"}`}>{pasa ? "Pasa" : "Revisar"}</span>
                  </div>
                  <div className="faint" style={{ fontSize: 11.5, margin: "2px 0 6px" }}>{SUB[dim]}</div>
                  <Rows checks={checks} prefix={dim} />
                </div>
              );
            })}
          </div>
        </>
      )}

      {layout === "C" && (
        <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 16, alignItems: "start" }}>
          {preview}
          <div className="card">
            {(["identidad", "completitud"] as const).map((dim) => {
              const checks = dim === "identidad" ? ident : compl;
              return (
                <div key={dim} style={{ marginBottom: 10 }}>
                  <div className="eyebrow" style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{dim === "identidad" ? "IDENTIDAD" : "COMPLETITUD"}</span>
                    <span className={`chip ${dimPasa(checks) ? "mat-ok" : "mat-amber"}`}>{dimPasa(checks) ? "Pasa" : "Revisar"}</span>
                  </div>
                  <Rows checks={checks} prefix={dim} />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

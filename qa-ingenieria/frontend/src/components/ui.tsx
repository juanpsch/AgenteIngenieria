import { useState } from "react";
import { Upload } from "lucide-react";
import type { Check, Veredicto } from "../api/client";
import { VERDICTS, MATURITY } from "../design/tokens";

export function Dropzone({ file, onFile, title, subtitle, size = 30 }: {
  file: File | null; onFile: (f: File | null) => void; title: string; subtitle?: string; size?: number;
}) {
  const [over, setOver] = useState(false);
  return (
    <label
      className={`dropzone ${file ? "has" : ""} ${over ? "over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0] || null); }}
    >
      <input type="file" hidden onChange={(e) => onFile(e.target.files?.[0] || null)} />
      <Upload size={size} color="var(--teal)" />
      <div className="t">{file ? file.name : title}</div>
      {subtitle && <div className="s">{subtitle}</div>}
    </label>
  );
}

export function MaturityBadge({ m }: { m?: string | null }) {
  const info = (MATURITY as Record<string, { label: string; cls: string }>)[m || "solo_reglas"] || MATURITY.solo_reglas;
  return <span className={`chip ${info.cls}`}>{info.label}</span>;
}

const BADGE: Record<string, string> = { pass: "b-pass", fail: "b-fail", warn: "b-warn", info: "b-info" };
const GLYPH: Record<string, string> = { pass: "✓", fail: "✕", warn: "!", info: "i" };
const STATE_LABEL: Record<string, string> = { pass: "cumple", fail: "no cumple", warn: "a revisar", info: "informativo" };

export function CheckRow({ c }: { c: Check }) {
  return (
    <div className="check">
      <div className={`badge ${BADGE[c.state]}`} role="img" aria-label={STATE_LABEL[c.state]} title={STATE_LABEL[c.state]}>{GLYPH[c.state]}</div>
      <div>
        <div className="lab">{c.label}</div>
        {c.detail && <div className="det">{c.detail}</div>}
      </div>
    </div>
  );
}

const VCLS: Record<string, string> = { ok: "v-ok", amber: "v-amber", red: "v-red", info: "v-info" };

export function VeredictoChip({ v }: { v: Veredicto }) {
  const info = VERDICTS[v] || VERDICTS.faltan_datos;
  const style: Record<string, string> = {
    ok: "mat-ok", amber: "mat-amber", red: "mat-red", info: "mat-neutral",
  };
  return <span className={`chip ${style[info.kind]}`} title={info.label}>{info.label}</span>;
}

export function VerdictBanner(props: {
  veredicto: Veredicto; resumen: string; fileName: string; tipo: string;
  score: number | null; noConcluyente: boolean;
}) {
  const v = VERDICTS[props.veredicto] || VERDICTS.faltan_datos;
  const hasScore = props.score != null && !props.noConcluyente;
  return (
    <div className={`verdict ${VCLS[v.kind]} ct-fade`}>
      <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
        <div className="glyph">{v.glyph}</div>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: ".6px" }}>VEREDICTO</div>
          <div className="label">{v.label}</div>
          <div className="resumen">{props.resumen}</div>
        </div>
      </div>
      <div style={{ textAlign: "right", paddingLeft: 18 }}>
        <div className="mono" style={{ fontSize: 12 }}>{props.fileName}</div>
        <div className="mono faint" style={{ fontSize: 11 }}>{props.tipo}</div>
        <div className="score">{hasScore ? props.score : "—"}<small>{hasScore ? "SIMILITUD" : "NO CALIBRADO"}</small></div>
      </div>
    </div>
  );
}

export function CajetinPreview({ bbox, imagen }: { bbox: { x: number; y: number; w: number; h: number } | null; imagen?: string | null }) {
  return (
    <div className="preview-ph" style={imagen ? { background: "#fff" } : undefined}>
      {imagen && <img src={imagen} alt="Página 1" style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }} />}
      {bbox && (
        <div
          className="cajetin-box"
          style={{ left: `${bbox.x * 100}%`, top: `${bbox.y * 100}%`, width: `${bbox.w * 100}%`, height: `${bbox.h * 100}%` }}
        >
          <span className="lab">Cajetín detectado</span>
        </div>
      )}
      {!imagen && !bbox && <div className="faint" style={{ padding: 16 }}>Previsualización del documento</div>}
    </div>
  );
}

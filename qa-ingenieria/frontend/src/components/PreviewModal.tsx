import type { BBox } from "../api/client";

export function PreviewModal({ src, title, tag, bbox, onClose }: {
  src: string; title: string; tag?: string; bbox?: BBox | null; onClose: () => void;
}) {
  return (
    <div className="overlay" onClick={onClose} style={{ alignItems: "center", justifyContent: "center" }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 12, width: 820, maxWidth: "94vw", maxHeight: "92vh", display: "flex", flexDirection: "column", boxShadow: "0 24px 60px rgba(0,0,0,.32)" }}>
        <div className="modal-h">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <b className="mono" style={{ fontSize: 13 }}>{title}</b>
            {tag && <span className="chip mat-neutral">{tag}</span>}
          </div>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 18, overflow: "auto", background: "var(--bg)", display: "flex", justifyContent: "center" }}>
          <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
            <img src={src} alt={title} style={{ maxWidth: "100%", maxHeight: "76vh", display: "block", borderRadius: 6, border: "1px solid var(--border2)", background: "#fff" }} />
            {bbox && (
              <div className="cajetin-box" style={{ left: `${bbox.x * 100}%`, top: `${bbox.y * 100}%`, width: `${bbox.w * 100}%`, height: `${bbox.h * 100}%` }}>
                <span className="lab">Cajetín detectado</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

import type { ReactNode } from "react";
import { X } from "lucide-react";
import { FACET_AXIS, FACET_ORDER } from "../design/facets";

// Ayuda en la UI: guía breve de las pantallas y conceptos. Espejo de docs/UI_Guia.md.
const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <div style={{ marginTop: 18 }}>
    <div style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: .6, color: "#0e7c86", textTransform: "uppercase", marginBottom: 6 }}>{title}</div>
    <div style={{ fontSize: 13, color: "#33454f", lineHeight: 1.55 }}>{children}</div>
  </div>
);
const Dot = ({ c }: { c: string }) => <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: c, marginRight: 5, verticalAlign: "middle" }} />;
const Pill = ({ children, bg, fg, border }: { children: ReactNode; bg: string; fg: string; border: string }) => (
  <span style={{ fontSize: 11.5, fontWeight: 600, color: fg, background: bg, border: `1px solid ${border}`, borderRadius: 20, padding: "1px 8px", margin: "0 2px" }}>{children}</span>
);

export function Help({ onClose }: { onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(12,32,48,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24 }}>
      <div onClick={(e) => e.stopPropagation()} className="cz-scroll" style={{ background: "#fff", borderRadius: 14, maxWidth: 780, width: "100%", maxHeight: "88vh", overflow: "auto", boxShadow: "0 20px 60px rgba(12,32,48,.3)" }}>
        <div style={{ position: "sticky", top: 0, background: "linear-gradient(180deg,#f8fafb,#fff)", borderBottom: "1px solid #eef2f4", padding: "16px 22px", display: "flex", alignItems: "center", gap: 12, zIndex: 1 }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#13252f" }}>Ayuda — Cotejar</h2>
          <div style={{ flex: 1 }} />
          <button title="Cerrar" onClick={onClose} style={{ border: "none", background: "#eef1f3", width: 30, height: 30, borderRadius: 8, cursor: "pointer", color: "#5d7180", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={16} /></button>
        </div>

        <div style={{ padding: "8px 22px 24px" }}>
          <Section title="Qué es">
            Cotejar controla la <b>admisión</b> y la <b>revisión de contenido</b> de documentos técnicos
            (P&IDs, planos, memorias, hojas de datos, esquemáticos). Primero verifica que el documento <i>sea
            lo que dice ser</i> (gate), y luego que su <i>contenido cumpla</i> reglas y normas.
          </Section>

          <Section title="Validar documento">
            Subís un PDF y elegís un <b>template</b>. Corre el <b>gate de admisión</b> (rápido, mira la
            portada/cajetín) → 🟢 válido · 🟡 revisión manual · 🔴 inválido. Si se admite, arranca la
            <b> revisión de contenido</b> (todo el documento) con hallazgos ubicados sobre cada hoja. Podés
            pedir una <b>observación visual (IA)</b> a demanda para P&IDs/planos.
          </Section>

          <Section title="Templates de referencia">
            Cada <b>template</b> es una <b>familia</b> de documento: define su tipo, qué reglas/normas exige y
            con qué ejemplos calibra el reconocimiento. Las familias se ubican por <b>facetas</b> (ejes
            ortogonales), no en un árbol fijo:
            <div style={{ margin: "8px 0", display: "flex", flexWrap: "wrap", gap: 12 }}>
              {FACET_ORDER.map((k) => <span key={k} style={{ fontSize: 12.5 }}><Dot c={FACET_AXIS[k].color} />{FACET_AXIS[k].label}</span>)}
            </div>
            <b>Pivot (tabla dinámica):</b> en "Agrupar en orden" elegís el <b>orden de los ejes</b> (reordená
            con ◀ ›, sumá con <i>+ Eje</i>, quitá con ✕) y la lista se agrupa <b>anidada</b> y <b>colapsable</b>.
            <br /><b>Madurez (calibración por ejemplos):</b> {" "}
            <Pill bg="#eef1f4" fg="#5b6b78" border="#dce3e8">Solo reglas</Pill> (0–1) →
            <Pill bg="#fdf4e3" fg="#946312" border="#f0ddb6">Calibrando</Pill> (2–4) →
            <Pill bg="#e4f4ee" fg="#0d6b53" border="#c3e7da">Calibrado</Pill> (5+, decisivo). Una familia nueva
            puede <b>heredar</b> ejemplos de su familia genérica mientras no tenga propios (↳ hereda…).
            <br /><b>3 vistas</b> (selector arriba): <b>A</b> tabla · <b>B</b> pivot + panel de detalle ·
            <b> C</b> tarjetas.
          </Section>

          <Section title="Observatorio de reglas">
            Planilla de <b>todas las reglas</b> con su <b>% de cumplimiento</b> (sobre lo verificable) por
            documento y por familia, más el <b>feedback humano</b>. Se pivotea por <b>Norma · Severidad ·
            Disciplina</b> (igual que Templates). Expandí una regla para ver el <b>desglose por familia</b>.
            <br />Feedback: {" "}
            <Pill bg="#e9f5f0" fg="#0d6b53" border="#c3e7da">👍 de acuerdo</Pill>
            <Pill bg="#f4f6f8" fg="#5b6b78" border="#dce3e8">🚫 no aplica</Pill>
            <Pill bg="#fdf6ea" fg="#946312" border="#f0ddb6">⚠ regla mal</Pill>. El indicador
            {" "}<Pill bg="#eef7f8" fg="#0b6b74" border="#bfe0e4">↗ norma</Pill> señala juicios con
            <b> alcance</b> norma/global, que se reusan en todas las familias que usan la regla.
          </Section>

          <Section title="Historial y auditoría">
            Todas las validaciones registradas, con <b>resumen</b> (validados / % aprobación / pendientes /
            promovidos) y filtros por <b>veredicto</b> y texto. Clic en una fila abre el <b>detalle</b> del
            análisis; un revisor sénior puede <b>sobrescribir</b> la decisión y <b>promover</b> el documento a
            referencia (mejora el template) o marcarlo como <b>contra-ejemplo</b>.
          </Section>

          <Section title="Conceptos clave">
            <b>Facetas:</b> coordenadas de una familia; las reglas se componen de todas (lo más específico
            gana). <b>Calibración:</b> el reconocimiento aprende de ejemplos (CLIP, sin re-entrenar); más
            ejemplos = más confiable. <b>Juicio con alcance:</b> al marcar tu juicio sobre una regla elegís
            si vale para <i>esta familia</i> o para <i>toda la norma</i>. El sistema <b>nunca inventa un
            "cumple"</b>: si no puede medir algo lo marca <i>no verificable</i>.
          </Section>
        </div>
      </div>
    </div>
  );
}

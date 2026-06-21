import { useEffect, useState } from "react";
import { Sidebar, type Section } from "./components/Sidebar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Validar } from "./screens/Validar";
import { Templates } from "./screens/Templates";
import { Reglas } from "./screens/Reglas";
import { Historial } from "./screens/Historial";
import { Help } from "./components/Help";
import { api } from "./api/client";
import { HelpCircle } from "lucide-react";

const HEAD: Record<Section, { h1: string; p: string }> = {
  validar: { h1: "Validar documento", p: "Subí un documento y cotejalo contra un template de referencia." },
  templates: { h1: "Templates de referencia", p: "Definí tipos de documento, sus reglas y ejemplos de calibración." },
  reglas: { h1: "Observatorio de reglas", p: "Estadística de cumplimiento por regla, facetada, con el feedback humano." },
  historial: { h1: "Historial y auditoría", p: "Validaciones registradas y métricas." },
};

export default function App() {
  const [section, setSection] = useState<Section>("validar");
  const [pendientes, setPendientes] = useState(0);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    api.historial().then((h) => setPendientes(h.metricas.pendientes)).catch(() => {});
  }, [section]);

  const head = HEAD[section];
  return (
    <>
      <Sidebar section={section} onNav={setSection} pendientes={pendientes} />
      <div className="main">
        <div className="header" style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1>{head.h1}</h1>
            <p>{head.p}</p>
          </div>
          <button title="Ayuda y guía de uso" onClick={() => setShowHelp(true)}
            style={{ flex: "none", display: "flex", alignItems: "center", gap: 6, border: "1px solid #dce3e8", background: "#fff", color: "#0e7c86", fontSize: 13, fontWeight: 600, padding: "7px 12px", borderRadius: 9, cursor: "pointer" }}>
            <HelpCircle size={16} /> Ayuda
          </button>
        </div>
        <div className="container">
          <ErrorBoundary key={section}>
            {section === "validar" && <Validar />}
            {section === "templates" && <Templates />}
            {section === "reglas" && <Reglas />}
            {section === "historial" && <Historial />}
          </ErrorBoundary>
        </div>
      </div>
      {showHelp && <Help onClose={() => setShowHelp(false)} />}
    </>
  );
}

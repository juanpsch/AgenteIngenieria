import { useEffect, useState } from "react";
import { Sidebar, type Section } from "./components/Sidebar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Validar } from "./screens/Validar";
import { Templates } from "./screens/Templates";
import { Historial } from "./screens/Historial";
import { api } from "./api/client";

const HEAD: Record<Section, { h1: string; p: string }> = {
  validar: { h1: "Validar documento", p: "Subí un documento y cotejalo contra un template de referencia." },
  templates: { h1: "Templates de referencia", p: "Definí tipos de documento, sus reglas y ejemplos de calibración." },
  historial: { h1: "Historial y auditoría", p: "Validaciones registradas y métricas." },
};

export default function App() {
  const [section, setSection] = useState<Section>("validar");
  const [pendientes, setPendientes] = useState(0);

  useEffect(() => {
    api.historial().then((h) => setPendientes(h.metricas.pendientes)).catch(() => {});
  }, [section]);

  const head = HEAD[section];
  return (
    <>
      <Sidebar section={section} onNav={setSection} pendientes={pendientes} />
      <div className="main">
        <div className="header">
          <h1>{head.h1}</h1>
          <p>{head.p}</p>
        </div>
        <div className="container">
          <ErrorBoundary key={section}>
            {section === "validar" && <Validar />}
            {section === "templates" && <Templates />}
            {section === "historial" && <Historial />}
          </ErrorBoundary>
        </div>
      </div>
    </>
  );
}

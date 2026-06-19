import { ShieldCheck, Layers, Clock } from "lucide-react";

export type Section = "validar" | "templates" | "historial";

export function Sidebar({ section, onNav, pendientes }: { section: Section; onNav: (s: Section) => void; pendientes: number }) {
  const Item = ({ id, label, Icon }: { id: Section; label: string; Icon: typeof Clock }) => (
    <div
      className={`nav-item ${section === id ? "active" : ""}`}
      role="button"
      tabIndex={0}
      aria-current={section === id}
      onClick={() => onNav(id)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onNav(id); } }}
    >
      <Icon size={17} />
      <span>{label}</span>
    </div>
  );
  return (
    <div className="sidebar">
      <div className="brand">
        <div className="logo"><ShieldCheck size={18} /></div>
        <div>
          <div className="t">Cotejar</div>
          <div className="s">GATE DE ADMISIÓN</div>
        </div>
      </div>
      <div className="nav-group">
        <div className="nav-h">FLUJO</div>
        <Item id="validar" label="Validar documento" Icon={ShieldCheck} />
      </div>
      <div className="nav-group">
        <div className="nav-h">ADMINISTRACIÓN</div>
        <Item id="templates" label="Templates de referencia" Icon={Layers} />
        <Item id="historial" label="Historial y auditoría" Icon={Clock} />
      </div>
      <div className="side-foot">
        <div className="pend">
          <div className="l">PENDIENTES DE REVISIÓN</div>
          <div className="n">{pendientes}</div>
        </div>
        <div className="user">
          <div className="avatar">MR</div>
          <div>
            <div style={{ color: "#fff", fontSize: 12, fontWeight: 600 }}>M. Rossi</div>
            <div className="s">Mesa de admisión</div>
          </div>
        </div>
      </div>
    </div>
  );
}

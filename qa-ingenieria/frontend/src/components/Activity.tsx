import { createContext, useContext, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, Check, X, Loader } from "lucide-react";

type Kind = "run" | "ok" | "err";
interface Entry { id: number; msg: string; kind: Kind; }
interface Ctx {
  busy: boolean;
  current: string;
  log: Entry[];
  /** Corre `fn` mostrando `label` (y opcionalmente pasos que avanzan mientras espera). */
  run: <T>(label: string, fn: () => Promise<T>, steps?: string[]) => Promise<T>;
}

const ActivityCtx = createContext<Ctx | null>(null);
export const useActivity = (): Ctx => useContext(ActivityCtx) as Ctx;

let _id = 0;

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState("");
  const [log, setLog] = useState<Entry[]>([]);
  const timer = useRef<number>();
  const upd = (id: number, msg: string, kind: Kind) =>
    setLog((l) => l.map((e) => (e.id === id ? { ...e, msg, kind } : e)));

  async function run<T>(label: string, fn: () => Promise<T>, steps: string[] = []): Promise<T> {
    const id = ++_id;
    setBusy(true);
    setCurrent(steps[0] || label);
    // Una sola fila por operación: arranca como "run" (spinner) y muta a ok/err al terminar.
    setLog((l) => [{ id, msg: label, kind: "run" as Kind }, ...l].slice(0, 40));
    let i = 0;
    if (steps.length > 1) {
      timer.current = window.setInterval(() => { i = Math.min(i + 1, steps.length - 1); setCurrent(steps[i]); }, 1100);
    }
    try {
      const r = await fn();
      upd(id, label + " — listo", "ok");
      return r;
    } catch (e) {
      upd(id, label + " — error: " + String((e as Error)?.message || e), "err");
      throw e;
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      setBusy(false);
      setCurrent("");
    }
  }

  return (
    <ActivityCtx.Provider value={{ busy, current, log, run }}>
      {children}
      <ActivityWidget busy={busy} current={current} log={log} />
    </ActivityCtx.Provider>
  );
}

const ICON: Record<Kind, ReactNode> = {
  run: <Loader size={13} className="act-spin" color="var(--teal)" />,
  ok: <Check size={13} color="var(--green)" />,
  err: <X size={13} color="var(--red)" />,
};

function ActivityWidget({ busy, current, log }: { busy: boolean; current: string; log: Entry[] }) {
  const [open, setOpen] = useState(false);
  if (!busy && log.length === 0) return null;
  return (
    <div className="activity">
      <div className="activity-h" onClick={() => setOpen((o) => !o)}>
        {busy ? <Loader size={14} className="act-spin" color="var(--teal)" /> : <Check size={14} color="var(--green)" />}
        <span className="activity-cur">{busy ? current || "Trabajando…" : "Actividad"}</span>
        {log.length > 0 && <span className="activity-badge">{log.length}</span>}
        {open ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
      </div>
      {open && (
        <div className="activity-log">
          {log.map((e) => (
            <div key={e.id} className="activity-row">
              <span style={{ flex: "none", width: 14 }}>{ICON[e.kind]}</span>
              <span style={{ color: e.kind === "err" ? "var(--red-ink)" : "var(--ink2)" }}>{e.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { Component, type ReactNode } from "react";

/** Atrapa errores de render de una vista y muestra un mensaje en vez de dejar la pantalla en
 *  blanco. Reseteá montándolo con un `key` que cambie (p. ej. la sección activa). */
export class ErrorBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };

  static getDerivedStateFromError(err: Error) {
    return { err };
  }
  componentDidCatch(err: Error) {
    // eslint-disable-next-line no-console
    console.error("UI error:", err);
  }

  render() {
    if (this.state.err) {
      return (
        <div className="card ct-fade" style={{ borderColor: "var(--red-border)" }}>
          <div className="dim-h" style={{ color: "var(--red-ink)" }}>Algo se rompió en esta vista</div>
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>
            {String(this.state.err.message || this.state.err)}
          </div>
          <button className="btn btn-ghost" onClick={() => this.setState({ err: null })}>Reintentar</button>
        </div>
      );
    }
    return this.props.children;
  }
}

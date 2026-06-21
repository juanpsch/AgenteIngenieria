"""Informe de revisión en PDF (Cotejar). Toma un dict con el resultado del caso y arma un PDF paginado
con fuentes base (Helvetica). No importa nada del grafo: el endpoint arma el dict y lo pasa acá.

Uso: `generar_informe(datos) -> bytes` (PDF). Degrada con gracia si falta data.
"""

from __future__ import annotations

from typing import Any

_W, _H, _M = 595.0, 842.0, 56.0           # A4 en puntos + margen
_MAXW = _W - 2 * _M
_EST = {"ok": "[OK]", "fallo": "[FALLA]", "advertencia": "[!]", "no_verificable": "[n/v]"}


def _san(s: Any) -> str:
    """Reemplaza glifos que la fuente base no tiene y cae a Latin-1 (Helvetica embebida)."""
    s = (str(s if s is not None else ""))
    for a, b in (("→", "->"), ("✓", "ok"), ("✕", "x"), ("ⓘ", "(i)"), ("…", "..."), ("•", "-"),
                 ("—", "-"), ("–", "-")):
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


class _Doc:
    def __init__(self) -> None:
        import fitz
        self._fitz = fitz
        self.doc = fitz.open()
        self.page = self.doc.new_page(width=_W, height=_H)
        self.y = _M

    def _ensure(self, h: float) -> None:
        if self.y + h > _H - _M:
            self.page = self.doc.new_page(width=_W, height=_H)
            self.y = _M

    def _wrap(self, s: str, size: float, fn: str) -> list[str]:
        out: list[str] = []
        for para in _san(s).split("\n"):
            cur = ""
            for w in para.split(" "):
                t = (cur + " " + w).strip()
                if self._fitz.get_text_length(t, fontname=fn, fontsize=size) <= _MAXW - 4:
                    cur = t
                else:
                    if cur:
                        out.append(cur)
                    cur = w
            out.append(cur)
        return out

    def text(self, s: str, size: float = 9.5, bold: bool = False, color=(0, 0, 0), gap: float = 3.0, indent: float = 0.0) -> None:
        fn = "hebo" if bold else "helv"
        for ln in self._wrap(s, size, fn):
            self._ensure(size + gap)
            self.page.insert_text((_M + indent, self.y + size), ln, fontsize=size, fontname=fn, color=color)
            self.y += size + gap

    def space(self, h: float = 6.0) -> None:
        self.y += h

    def rule(self) -> None:
        self._ensure(10)
        self.page.draw_line((_M, self.y), (_W - _M, self.y), color=(0.8, 0.84, 0.84), width=0.6)
        self.y += 8

    def bytes(self) -> bytes:
        return self.doc.tobytes()


def generar_informe(datos: dict) -> bytes:
    d = _Doc()
    d.text("Informe de revisión — Cotejar", size=16, bold=True)
    if datos.get("fecha"):
        d.text(f"Fecha: {datos['fecha']}", size=9, color=(0.4, 0.4, 0.4))
    d.space(4); d.rule()

    d.text("Documento", size=11, bold=True)
    d.text(f"Archivo: {datos.get('filename', '-')}")
    d.text(f"Tipo / familia: {datos.get('tipo', '-')}")
    d.space(4)

    d.text("Admisión (Fase 0)", size=11, bold=True)
    sc = datos.get("score")
    d.text(f"Veredicto: {datos.get('admision', '-')}" + (f"   ·   score {sc}" if sc is not None else ""))
    d.space(4)

    rev = datos.get("revision") or {}
    d.text("Revisión de contenido (Fase 1)", size=11, bold=True)
    if rev:
        linea = f"Veredicto: {rev.get('verdicto', '-')}"
        if rev.get("severidad_max"):
            linea += f"   ·   severidad máx: {rev['severidad_max']}"
        if rev.get("confiabilidad"):
            linea += f"   ·   confiabilidad: {rev['confiabilidad']}"
        d.text(linea)
        if rev.get("resuelta"):
            d.text("Revisión resuelta por un humano.", size=9, color=(0.4, 0.4, 0.4))
    else:
        d.text("No se corrió la revisión de contenido.", color=(0.4, 0.4, 0.4))
    d.space(4)

    hall = datos.get("hallazgos") or []
    duros = [h for h in hall if h.get("fuente") != "vlm"]
    vlm = [h for h in hall if h.get("fuente") == "vlm"]

    if duros:
        d.text("Hallazgos (reglas)", size=11, bold=True)
        dims: dict[str, list] = {}
        for h in duros:
            dims.setdefault(h.get("dimension") or "otros", []).append(h)
        for dim, hs in dims.items():
            d.space(2); d.text(dim.upper(), size=9, bold=True, color=(0.3, 0.3, 0.3))
            for h in hs:
                est = _EST.get(h.get("estado"), h.get("estado", "?"))
                sev = h.get("severidad", "")
                d.text(f"{est} {h.get('razonamiento') or h.get('check_id')}  ({sev})", indent=8)
                if h.get("evidencia"):
                    d.text(f"evidencia: {h['evidencia']}", size=8.5, color=(0.35, 0.35, 0.35), indent=20)
                if h.get("estado_previo"):
                    d.text(f"verificado por IA: {h.get('estado_previo')} -> {h.get('estado')}. {h.get('nota_vlm', '')}",
                           size=8.5, color=(0.15, 0.35, 0.7), indent=20)
        d.space(4)

    if vlm:
        d.text("Observación visual (IA)", size=11, bold=True)
        for h in vlm:
            d.text(f"- [{h.get('severidad', '')}] {h.get('evidencia', '')}", indent=8)
        d.space(4)

    d.rule()
    d.text("Decisión humana", size=11, bold=True)
    dec = {"approved": "Admitido", "rejected": "No admitido"}.get(datos.get("decision"), "Sin decisión registrada")
    d.text(dec)
    if datos.get("notas"):
        d.text(f"Notas: {datos['notas']}", size=9, color=(0.4, 0.4, 0.4))

    return d.bytes()

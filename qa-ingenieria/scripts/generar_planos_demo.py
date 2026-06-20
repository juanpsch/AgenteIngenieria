"""Genera planos sintéticos (PDF con capa de texto) para PROBAR la norma iram-dibujo en distintos
niveles de cumplimiento. Salida en tests/fixtures/docs/_sinteticos/ (gitignored). Reproducible:
    uv run python scripts/generar_planos_demo.py

- plano_cumple.pdf       → cumple todo (rótulo, escala normalizada, cotas mm, proyección)
- plano_parcial.pdf      → cumple casi todo, falla 'cositas' (escala 1:30 no normalizada, cotas en cm, sin proyección)
- plano_no_cumple.pdf    → no declara IRAM, sin rótulo, sin escala, sin mm
"""

from __future__ import annotations

import sys
from pathlib import Path

_DEST = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "docs" / "_sinteticos"

PLANOS = {
    "plano_cumple.pdf": [
        "PLANO DE PLANTA — INSTALACION",
        "Confeccionado segun Norma IRAM 4504 / IRAM 4513.",
        "Metodo de proyeccion: ISO (E) - primer diedro.",
        "",
        "ROTULO",
        "Denominacion: Planta general del edificio",
        "N de plano: PL-001    Revision: B",
        "Escala: 1:50",
        "Fecha: 2026-06-19",
        "Dibujo: J. Perez    Reviso: M. Gomez    Aprobo: A. Diaz",
        "",
        "Acotacion en mm (IRAM 4513). Cotas en mm salvo indicacion contraria.",
        "Cota: 1200 mm    Cota: 450 mm    Cota: 75 mm",
    ],
    "plano_parcial.pdf": [
        "PLANO - ESQUEMA DE DETALLE",
        "Segun IRAM 4504.",
        "",
        "Denominacion: Esquema parcial",
        "N de plano: PL-014",
        "Escala: 1:30",                       # NO normalizada
        "Dibujo: J. Perez    Reviso: M. Gomez",  # sin 'Aprobo' (igual son 2 -> pasa responsables)
        "",
        "Medidas en cm.",                      # cm, no mm
        "Medida: 120 cm    Medida: 45 cm",
        # sin metodo de proyeccion declarado
    ],
    "plano_no_cumple.pdf": [
        "CROQUIS A MANO ALZADA",
        "Boceto preliminar, medidas tentativas.",
        "Sin normalizar. Documento de trabajo interno.",
        "Observaciones varias del autor.",
    ],
}


def _pdf(path: Path, lineas: list[str]) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 en puntos
    page.draw_rect(fitz.Rect(30, 30, 565, 812), color=(0, 0, 0), width=1)  # marco (no en blanco)
    y = 70
    for ln in lineas:
        if ln:
            page.insert_text((50, y), ln, fontsize=12, color=(0, 0, 0))
        y += 22
    doc.save(str(path))


def main() -> int:
    _DEST.mkdir(parents=True, exist_ok=True)
    for nombre, lineas in PLANOS.items():
        _pdf(_DEST / nombre, lineas)
        print(f"  [OK] {nombre}")
    print(f"\n{len(PLANOS)} planos en {_DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

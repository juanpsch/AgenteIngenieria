"""Extrae los DIAGRAMAS (P&ID / lazos) que viven dentro de libros/guías y los guarda como documentos
sueltos, ordenados por carpeta. Así obtenemos láminas P&ID reales (que SÍ cruzan el gate) a partir de
documentos que, enteros, no son diagramas sino memorias/guías con figuras adentro.

Las páginas fueron verificadas visualmente (render + inspección). Reproducible:
    uv run python scripts/extraer_pids.py

Salida (gitignored, como el resto de docs/):
    instrumentacion/pid/        -> P&IDs y diagramas de proceso
    instrumentacion/leyendas/   -> tablas de símbolos / letras ISA
"""

from __future__ import annotations

import sys
from pathlib import Path

_DOCS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "docs"

# (archivo_fuente, [páginas 1-based], salida)   — todas relativas a tests/fixtures/docs/
EXTRACCIONES = [
    # P&ID / diagramas de proceso
    ("instrumentacion/pid_kimray.pdf",    [2],            "instrumentacion/pid/kimray_pid_sample.pdf"),
    ("instrumentacion/pid_kimray.pdf",    [3],            "instrumentacion/pid/kimray_pfd_sample.pdf"),
    ("instrumentacion/instr_isa_ch7.pdf", [26],           "instrumentacion/pid/isa_control_columna_reactor.pdf"),
    ("instrumentacion/instr_isa_ch7.pdf", [27],           "instrumentacion/pid/isa_recycle_tank.pdf"),
    # Leyendas / tablas de símbolos
    ("instrumentacion/pid_kimray.pdf",    [10, 11, 12, 13], "instrumentacion/leyendas/kimray_simbolos_equipos.pdf"),
    ("instrumentacion/instr_utn_frrq.pdf", [8],           "instrumentacion/leyendas/utn_simbolos_letras_isa.pdf"),
    # P&ID reales de gas argentino (EIA Planta Compresora Salliqueló) → positivos del genérico
    ("instrumentacion/fuentes/salliquelo_eia.pdf", [231], "instrumentacion/pid_validos/salliquelo_pid_1.pdf"),
    ("instrumentacion/fuentes/salliquelo_eia.pdf", [232], "instrumentacion/pid_validos/salliquelo_pid_2.pdf"),
    ("instrumentacion/fuentes/salliquelo_eia.pdf", [233], "instrumentacion/pid_validos/salliquelo_pid_3.pdf"),
]


def _extraer(src: Path, paginas: list[int], dest: Path) -> str:
    import fitz

    doc = fitz.open(str(src))
    out = fitz.open()
    for n in paginas:
        if 1 <= n <= doc.page_count:
            out.insert_pdf(doc, from_page=n - 1, to_page=n - 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dest))
    return f"{out.page_count} pág"


def main() -> int:
    hechos = 0
    for src_rel, paginas, dest_rel in EXTRACCIONES:
        src = _DOCS / src_rel
        if not src.exists():
            print(f"  [--] {dest_rel:48} (falta fuente {src_rel} — corré descargar_fixtures.py)")
            continue
        info = _extraer(src, paginas, _DOCS / dest_rel)
        print(f"  [OK] {dest_rel:48} {info}  <- {src_rel} p{paginas}")
        hechos += 1
    print(f"\n{hechos}/{len(EXTRACCIONES)} extraídos en {_DOCS}")
    return 0 if hechos else 1


if __name__ == "__main__":
    sys.exit(main())

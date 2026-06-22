"""Divide los CUADERNILLOS de planos de arquitectura de vivienda (juegos de láminas municipales) en
láminas sueltas, una por página — como hicimos con los P&IDs. Así la familia 'plano_arquitectura_vivienda'
obtiene >20 láminas reales (plantas/cortes/vistas) para calibrar.

Las fuentes (caso: fuente en el manifest) se bajan con descargar_fixtures.py a
    tests/fixtures/docs/civil/arq_vivienda_src/
y este script las explota página a página a:
    tests/fixtures/docs/civil/arq_vivienda/<prefijo>_pNN.pdf   (gitignored, como el resto de docs/)

Nota: algunas páginas de un cuadernillo no son láminas (índice, memoria, planillas). Al PROMOVER positivos
para calibrar la familia, elegí las que sean láminas reales — es una acción humana deliberada.

Reproducible:  uv run python scripts/extraer_planos_arq.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_DOCS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "docs"
_OUT = "civil/arq_vivienda"
_MAX = 60  # tope de seguridad por fuente (no explotar PDFs de cientos de páginas)

# (archivo_fuente relativo a docs/, prefijo de salida) — se explota CADA página
FUENTES = [
    ("civil/arq_vivienda_src/arq_ipv_oasis_det.pdf", "arq_ipv_oasis_det"),
    ("civil/arq_vivienda_src/arq_ipv_cpropia.pdf",   "arq_ipv_cpropia"),
    ("civil/arq_vivienda_src/arq_oliva_sur.pdf",     "arq_oliva_sur"),
    ("civil/arq_vivienda_src/arq_ruv_casa3.pdf",     "arq_ruv_casa3"),
    ("civil/arq_vivienda_src/arq_mx_prototipos.pdf", "arq_mx_prototipos"),
    ("civil/arq_vivienda_src/arq_ipv_solar.pdf",     "arq_ipv_solar"),
    ("civil/arq_vivienda_src/arq_ull_candelaria.pdf", "arq_ull_candelaria"),
]


def _explotar(src: Path, prefijo: str) -> int:
    import fitz

    doc = fitz.open(str(src))
    n = min(doc.page_count, _MAX)
    for i in range(n):
        out = fitz.open()
        out.insert_pdf(doc, from_page=i, to_page=i)
        dest = _DOCS / _OUT / f"{prefijo}_p{i + 1:02d}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(str(dest))
    return n


def main() -> int:
    total = 0
    for src_rel, prefijo in FUENTES:
        src = _DOCS / src_rel
        if not src.exists():
            print(f"  [--] {src_rel:46} (falta — corré descargar_fixtures.py)")
            continue
        n = _explotar(src, prefijo)
        print(f"  [OK] {prefijo:24} -> {n:>2} láminas  <- {src_rel}")
        total += n
    print(f"\n{total} láminas en {_DOCS / _OUT}")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())

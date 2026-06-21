"""Genera las IMÁGENES DE REFERENCIA de las normas (leyendas/estándares que el VLM usa como ground-truth
para juzgar las reglas gráficas), renderizándolas desde los fixtures. Salida en knowledge/normas/refs/
(gitignored). Reproducible:
    uv run python scripts/generar_refs_normas.py

Cada norma que tenga `vlm.referencia_imagen: knowledge/normas/refs/<x>.png` necesita su imagen acá.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_OUT = _BASE / "knowledge" / "normas" / "refs"

# (PDF fuente relativo a la raíz, página 1-based, nombre de salida)
REFS = [
    ("tests/fixtures/docs/instrumentacion/pid_validos/pid_camuzzi_simbologia.pdf", 1, "camuzzi_simbologia.png"),
    ("tests/fixtures/docs/instrumentacion/fuentes/camuzzi_glosario.pdf", 14, "camuzzi_glosario.png"),  # símbolos instrum./válvulas/actuadores
    # EPA WWTP: hojas de leyenda del juego (P-001/002/003)
    ("tests/fixtures/docs/instrumentacion/pid_validos/pid_epa_wwtp.pdf", 6, "epa_legend_1.png"),
    ("tests/fixtures/docs/instrumentacion/pid_validos/pid_epa_wwtp.pdf", 7, "epa_legend_2.png"),
    ("tests/fixtures/docs/instrumentacion/pid_validos/pid_epa_wwtp.pdf", 8, "epa_legend_3.png"),
]


def main() -> int:
    import fitz

    _OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for src_rel, pg, out_name in REFS:
        src = _BASE / src_rel
        if not src.exists():
            print(f"  [--] {out_name} (falta fuente {src_rel} — corré descargar_fixtures.py)")
            continue
        d = fitz.open(str(src))
        d[min(pg, d.page_count) - 1].get_pixmap(dpi=150).save(str(_OUT / out_name))
        print(f"  [OK] {out_name}  <- {src_rel} p{pg}")
        n += 1
    print(f"\n{n}/{len(REFS)} imágenes de referencia en {_OUT}")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())

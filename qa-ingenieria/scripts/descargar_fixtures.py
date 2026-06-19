"""Descarga los documentos de prueba (públicos) definidos en tests/fixtures/manifest.yaml.

Los PDFs son binarios grandes de sitios externos: NO se commitean (están gitignored). Este script
los baja a tests/fixtures/docs/ para poder probar la revisión de contenido localmente, de forma
reproducible. Uso:  uv run python scripts/descargar_fixtures.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import yaml

_BASE = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
_DOCS = _BASE / "docs"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def descargar(url: str, dest: Path) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (URLs del manifest, no input)
            data = r.read()
        if not data:
            return False, "vacío"
        dest.write_bytes(data)
        return True, f"{len(data) / 1024:.0f} KB"
    except Exception as exc:  # red flaky / 403 / 404
        return False, str(exc)[:80]


def main() -> int:
    manifest = yaml.safe_load((_BASE / "manifest.yaml").read_text(encoding="utf-8"))
    _DOCS.mkdir(parents=True, exist_ok=True)
    ok = 0
    for d in manifest.get("docs", []):
        dest = _DOCS / d["archivo"]
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  [==] {d['archivo']} (ya existe)")
            ok += 1
            continue
        bien, info = descargar(d["url"], dest)
        print(f"  [{'OK' if bien else '--'}] {d['archivo']:30} {info}")
        ok += bien
    print(f"\n{ok}/{len(manifest.get('docs', []))} disponibles en {_DOCS}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

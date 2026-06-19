"""Genera archivos de prueba para validar el agente (Fase 0).

Crea en sandbox/test_fixtures/:
- memoria_calculo_P102.pdf  (memoria de cálculo, texto) -> entrega 'calculo' completa
- plano_P102.pdf            (plano, texto tipo rótulo)   -> entrega 'fabricacion' (sin lista = INCOMPLETA)
- lista_materiales_P102.xlsx (LDM)                       -> completa la entrega 'fabricacion'
- presupuesto.pdf           (irrelevante)                -> NO_ADMISIBLE
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("sandbox/test_fixtures")
OUT.mkdir(parents=True, exist_ok=True)


def _pdf(path: Path, texto: str) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), texto, fontsize=11)
    doc.save(str(path))
    doc.close()


def main() -> None:
    _pdf(OUT / "memoria_calculo_P102.pdf", (
        "MEMORIA DE CALCULO ESTRUCTURAL\n"
        "Proyecto P-102  Rev B\n\n"
        "1. Hipotesis y cargas\n"
        "Carga muerta 5 kN/m2, sobrecarga de uso 3 kN/m2.\n\n"
        "2. Modelo estructural\n"
        "Portico de acero S275, luz 12 m.\n\n"
        "3. Verificaciones\n"
        "Tension maxima 180 MPa < 261 MPa OK. Flecha L/350 OK.\n\n"
        "4. Conclusiones\n"
        "La estructura verifica todas las solicitaciones."
    ))

    _pdf(OUT / "plano_P102.pdf", (
        "PLANO DE FABRICACION\n"
        "Proyecto: P-102   Rev: B   Escala: 1:50\n"
        "Detalle de union viga-columna. Despiece de chapas.\n"
        "Rotulo: Nave industrial P-102."
    ))

    _pdf(OUT / "presupuesto.pdf", (
        "PRESUPUESTO COMERCIAL\n"
        "Cliente: ACME. Validez 30 dias.\n"
        "Item 1: provision de acero - USD 12000.\n"
        "Item 2: mano de obra - USD 8000.\n"
        "Total: USD 20000. Esto NO es documentacion tecnica."
    ))

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "LDM"
    ws.append(["item", "descripcion", "cantidad", "material", "peso_kg"])
    ws.append([1, "Perfil IPE 300", 8, "S275", 252.0])
    ws.append([2, "Chapa 10mm", 16, "S275", 64.0])
    ws.append([3, "Bulon M20", 64, "8.8", 12.8])
    wb.save(str(OUT / "lista_materiales_P102.xlsx"))

    print("Fixtures generados en", OUT.resolve())
    for f in sorted(OUT.iterdir()):
        print(" -", f.name)


if __name__ == "__main__":
    main()

"""Smoke de la API Cotejar (validar -> guard promoción -> decisión -> promover -> historial)."""

from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8011"
TIPO = "esquematico_electronico"
PDF = "knowledge/tipos/filesTipos/PANDA_CARRIER.pdf"


def main() -> None:
    with open(PDF, "rb") as f:
        r = httpx.post(f"{BASE}/api/validar",
                       data={"tipo_doc": TIPO},
                       files={"file": ("PANDA_CARRIER.pdf", f, "application/pdf")},
                       timeout=180).json()
    tid = r["thread_id"]
    print(f"VALIDAR  : status={r['status']} veredicto={r['veredicto']} maturity={r['maturity']} "
          f"score={r['score']} checks={len(r['checks'])}")

    pg = httpx.post(f"{BASE}/api/tipos/{TIPO}/referencias/promover",
                    json={"thread_id": tid, "promote": True}, timeout=30)
    print(f"PROMOVER sin aprobar -> HTTP {pg.status_code} (esperado 409)")

    d = httpx.post(f"{BASE}/api/casos/{tid}/decision", json={"decision": "approved"}, timeout=30).json()
    print(f"DECISION : {d}")

    p = httpx.post(f"{BASE}/api/tipos/{TIPO}/referencias/promover",
                   json={"thread_id": tid, "promote": True}, timeout=30).json()
    print(f"PROMOVER : {p}")

    t = httpx.get(f"{BASE}/api/tipos/{TIPO}", timeout=30).json()
    print(f"TIPO     : refs_count={t['refs_count']} maturity={t['maturity']}")

    h = httpx.get(f"{BASE}/api/historial", timeout=30).json()
    print(f"HISTORIAL: metricas={h['metricas']} items={len(h['items'])}")


if __name__ == "__main__":
    main()

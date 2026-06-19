"""Diagnóstico del server del sandbox (127.0.0.1:7860).

Verifica ui.reply_field / ui.files_field y corre una ida y vuelta real
(plano -> incompleta -> lista -> completa) chequeando que el panel de
documentos acumule en vez de pisar.
"""

from __future__ import annotations

from pathlib import Path

import httpx

BASE = "http://127.0.0.1:7860"
FIX = Path("sandbox/test_fixtures")


def upload(sid: str, path: Path) -> dict:
    data = path.read_bytes()
    r = httpx.post(f"{BASE}/api/upload", params={"session_id": sid, "filename": path.name},
                   content=data, timeout=30)
    return r.json()


def turn(sid: str, text: str, attachment: dict | None) -> dict:
    body = {"session_id": sid, "text": text}
    if attachment:
        body["attachment"] = {"id": attachment["attachment_id"], "filename": attachment["filename"]}
    return httpx.post(f"{BASE}/api/turn", json=body, timeout=120).json()


def _panel(res: dict) -> list[str]:
    state = res.get("state") or {}
    return [c.get("titulo") for c in (state.get("documentos_panel") or [])]


def main() -> None:
    s = httpx.post(f"{BASE}/api/session", timeout=30).json()
    sid = s["session_id"]
    print("ui.reply_field =", s["ui"].get("reply_field"))
    print("ui.files_field =", s["ui"].get("files_field"))

    # Caso: DOS archivos adjuntados antes de enviar -> un solo turno
    upload(sid, FIX / "plano_P102.pdf")
    a2 = upload(sid, FIX / "lista_materiales_P102.xlsx")
    r = turn(sid, "Entrega de fabricación del P-102, estructural: plano + lista de materiales", a2)
    print("\nUN TURNO, 2 ARCHIVOS:", r.get("status"), "| panel =", _panel(r))


if __name__ == "__main__":
    main()

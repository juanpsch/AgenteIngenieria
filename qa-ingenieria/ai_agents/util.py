"""Utilidades compartidas de los agentes.

- `run_agent`: corre un Agent del SDK y devuelve el texto final.
- `extract_json`: parseo robusto de salidas LLM con **regex + fallback** (lección #7).
  Nunca `json.loads` directo sobre la salida del modelo.
- `load_prompt`: carga instrucciones desde `prompts/<name>.txt`.
- `build_input`: arma input multimodal (texto + imágenes) para visión.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# En Windows, el ProactorEventLoop emite ruido al cerrar sockets HTTP
# ("ConnectionResetError 10054" en _call_connection_lost). El SelectorEventLoop
# (el que ya usa Streamlit/Tornado) no tiene ese problema y soporta nuestras
# llamadas HTTP sin issues. Seteamos la policy una vez, al importar los agentes.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
MAX_IMAGES = 8


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def run_agent(agent: Any, input_data: Any) -> str:
    """Corre el agente de forma síncrona y devuelve `final_output` como string.

    Los nodos del grafo son sync (el sandbox usa `graph.stream`, sync). El SDK es
    async, así que envolvemos `Runner.run` con `asyncio.run`. Si ya hubiera un loop
    corriendo (p. ej. nodo sync invocado desde contexto async), lo derivamos a un
    thread con su propio loop para no chocar.

    Robustez: timeout por llamada (`LLM_TIMEOUT`, def. 90 s) y reintentos con backoff
    (`LLM_RETRIES`, def. 2) ante fallas transitorias (rate-limit, red, timeout).
    """
    import time

    from agents import Runner

    timeout = _env_int("LLM_TIMEOUT", 90)
    retries = _env_int("LLM_RETRIES", 2)

    async def _run() -> Any:
        return await asyncio.wait_for(Runner.run(agent, input_data), timeout=timeout)

    def _exec() -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(lambda: asyncio.run(_run())).result()

    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = _exec()
            out = result.final_output
            return out if isinstance(out, str) else str(out)
        except Exception as exc:  # noqa: BLE001 — reintenta cualquier fallo del SDK/red
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))  # backoff lineal
    raise last if last else RuntimeError("run_agent falló sin excepción")


def extract_json(text: str, default: dict) -> dict:
    """Extrae el primer objeto JSON del texto. Si no se puede, devuelve `default`."""
    if not isinstance(text, str):
        return dict(default)

    candidate = None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            candidate = brace.group(0)

    if not candidate:
        return dict(default)
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else dict(default)
    except Exception:
        return dict(default)


def build_input(text: str, imagenes: list[str] | None = None) -> Any:
    """Input para el Runner: string simple, o lista multimodal si hay imágenes."""
    if not imagenes:
        return text
    content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
    for url in imagenes[:MAX_IMAGES]:
        content.append({"type": "input_image", "image_url": url})
    return [{"role": "user", "content": content}]

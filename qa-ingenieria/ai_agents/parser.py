"""Parser del trigger (T0.10).

Del texto del trigger + nombres de archivos extrae los datos de la entrega
(tipo_entrega, disciplina, proyecto, revision). JSON con regex + fallback.
"""

from __future__ import annotations

from typing import Any

from ai_agents.provider import build_agent
from ai_agents.util import extract_json, load_prompt, run_agent

_PROMPT = load_prompt("parser")
_DEFAULT = {"tipo_entrega": None, "disciplina": None, "proyecto": None, "revision": None}


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def parse_trigger(trigger_text: str, filenames: list[str]) -> dict[str, Any]:
    agent = build_agent("parser-qa", instructions=_PROMPT, fast=True)
    listado = "\n".join(f"- {n}" for n in filenames) or "(sin archivos)"
    entrada = (
        f"Texto del trigger:\n{trigger_text or '(vacío)'}\n\n"
        f"Archivos adjuntos:\n{listado}"
    )
    text = run_agent(agent, entrada)
    data = extract_json(text, _DEFAULT)
    return {k: _norm(data.get(k)) for k in _DEFAULT}

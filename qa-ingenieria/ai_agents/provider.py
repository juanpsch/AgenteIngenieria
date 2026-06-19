"""Proveedor LLM configurable para los agentes (T0.0b).

Mantiene el OpenAI Agents SDK como runner, pero el modelo se arma desde env:
- LLM_PROVIDER=openai  -> modelo nativo del SDK (usa OPENAI_API_KEY).
- LLM_PROVIDER=claude  -> vía LiteLLM (usa ANTHROPIC_API_KEY).
- LLM_PROVIDER=litellm -> vía LiteLLM con el string de modelo tal cual (otros proveedores).

Helper único: `build_agent(...)` que todos los agentes usan, así cambiar de
proveedor es solo tocar el .env, sin tocar el código de los agentes.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "openai").strip().lower()


def _model_name(fast: bool) -> str:
    if fast:
        return os.getenv("LLM_MODEL_FAST") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    return os.getenv("LLM_MODEL") or "gpt-4o"


def build_model(fast: bool = False) -> Any:
    """Devuelve lo que el Agent del SDK acepta como `model`:
    un string (OpenAI directo) o un `LitellmModel` (resto de proveedores).
    """
    provider = _provider()
    model = _model_name(fast)

    if provider == "openai":
        # El SDK usa OPENAI_API_KEY del entorno.
        return model

    # Cualquier otro proveedor pasa por LiteLLM.
    from agents.extensions.models.litellm_model import LitellmModel

    if provider == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        litellm_model = model if "/" in model else f"anthropic/{model}"
    else:  # "litellm" genérico: el string de modelo ya trae el prefijo del proveedor
        api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        litellm_model = model

    return LitellmModel(model=litellm_model, api_key=api_key)


def build_agent(
    name: str,
    instructions: str,
    *,
    fast: bool = False,
    output_type: Optional[type] = None,
    **kwargs: Any,
):
    """Construye un `agents.Agent` con el modelo del proveedor configurado.

    Import perezoso de `agents` para no exigir el SDK en imports triviales/tests.
    """
    from agents import Agent

    agent_kwargs: dict[str, Any] = {
        "name": name,
        "instructions": instructions,
        "model": build_model(fast=fast),
    }
    if output_type is not None:
        agent_kwargs["output_type"] = output_type
    agent_kwargs.update(kwargs)
    return Agent(**agent_kwargs)

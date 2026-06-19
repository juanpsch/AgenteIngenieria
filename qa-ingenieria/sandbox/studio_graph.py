"""Grafo fakeado (all-fake) para LangGraph Studio / `langgraph dev`.

Studio/API aporta su propio checkpointer en runtime, por eso se anula acá.
"""

from dotenv import load_dotenv

load_dotenv()

from agent_sandbox.manifest import load_callable          # noqa: E402
from agent_sandbox.patcher import Patcher                  # noqa: E402
from agent_sandbox.runner import _instantiate_fakes        # noqa: E402

from sandbox.manifest import MANIFEST                       # noqa: E402

_fakes = _instantiate_fakes(MANIFEST)
_patcher = Patcher(MANIFEST)
_patcher.validate()
_patcher.apply(active={dep.name: False for dep in MANIFEST.dependencies}, fakes=_fakes)

graph = load_callable(MANIFEST.graph_factory)()
graph.checkpointer = None

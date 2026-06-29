# birblib -- the birb archetype layer on top of Big Little Mesh's frood.
#
# Big Little Mesh gave the fleet a pipeline for building pipelines: the bento (the unit of
# work), the banchan (an irreducible element), and a generated FSM the work flows through.
# every birb
# (magpie, grackle, sintra, liarbird, lloyd, ...) then re-improvised the same scaffold
# around it -- build a bento, walk the stages, pick a backend, write a manifest, watch an
# inbox, expose a CLI/daemon -- and the copies drifted. birblib is that scaffold, lifted
# once: a ported birb becomes a thin subclass, and a new birb is born small because it
# imports the lib instead of copying it.
#
# birblib depends on frood (the bus/mesh frood layer, generic to ALL pipelines)
# and knows nothing birb-specific. a birb declares its kind, banchans, and recipe, and
# implements ONE method -- cook(). everything below is the shared surface it builds on.

from birblib.bento import BirbBento, Manifest, state_name
from birblib.dispatch import Backend, NoBackendAvailable, dispatch
from birblib.driver import run
from birblib.handlers import BirbHandlers, CookResult
from birblib.names import safe_name
from birblib.stage import Stage

__all__ = [
    "Backend",
    "BirbBento",
    "BirbHandlers",
    "CookResult",
    "Manifest",
    "NoBackendAvailable",
    "Stage",
    "dispatch",
    "run",
    "safe_name",
    "state_name",
]

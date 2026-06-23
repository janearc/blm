# good_citizen.fsm -- the citizen-facing wrapper over the generated bento FSM harness.
# Re-exports the generated Handlers + step so a pipeline imports them from good_citizen
# rather than the gen tree, and run_step wires step() to the sidecar emitter (so a
# transition is relayed to the Go sidecar -> kafka). The generated harness is the source
# of truth; this is just the citizen seam onto it.
from bento.v1 import bento_fsm

from good_citizen import emit as _emit

# re-exports: a pipeline subclasses Handlers and calls step()/run_step().
Handlers = bento_fsm.Handlers
step = bento_fsm.step


def run_step(handlers, b, sidecar_url=None):
    # advance a bento ONE step, relaying the transition to the sidecar. The bus is the
    # loop: call this once per consumed event, not in an in-process loop -- so a process
    # may die between steps and another instance resumes from the bus.
    bento_fsm.step(handlers, _emit.sidecar_emitter(sidecar_url), b)

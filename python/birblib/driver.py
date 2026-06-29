# birblib.driver -- the standalone walk: drive a NOTICED bento to a terminal state.
#
# in production the bus is the loop -- one step per consumed event, a process may die
# between steps and another instance resumes from the bus (frood.run_step). this
# is the LOCAL counterpart, for a CLI run with no bus: step the FSM until a terminal
# handler is reached, relaying each transition to an optional emitter. it is the magpie
# process() loop, lifted so no birb re-writes it.

from bento.v1 import bento_pb2
from frood import fsm

from birblib.bento import BirbBento, Manifest

_TERMINAL = {bento_pb2.BENTO_STATE_DONE, bento_pb2.BENTO_STATE_FAILED}


def _pb(bento) -> bento_pb2.Bento:
    # accept a BirbBento or a bare bento_pb2.Bento, return the underlying protobuf.
    return bento.pb if isinstance(bento, BirbBento) else bento


def _walk(handlers, pb, emitter) -> None:
    # step `pb` to a terminal/resting state through the generated FSM, relaying each
    # transition to `emitter`. this is the one step-loop; run() (the CLI, raises on FAILED)
    # and service.drive (the daemon, returns on FAILED) share it and differ ONLY in the
    # post-walk policy. a handler that does not advance the state stops the walk rather than
    # spinning.
    while pb.state not in _TERMINAL:
        prev = pb.state
        fsm.step(handlers, emitter, pb)
        if pb.state == prev:
            break


def run(handlers, bento, emitter=None) -> Manifest | None:
    # drive `bento` (a BirbBento or a bare bento_pb2.Bento) to a terminal state, relaying
    # each transition to `emitter` when given (the CLI passes None -- local, no bus).
    # returns the handler's manifest (where the outputs are), NOT the bytes. raises
    # RuntimeError if the bento ends FAILED, so a caller surfaces the error rather than
    # reporting success.
    pb = _pb(bento)
    _walk(handlers, pb, emitter)
    if pb.state == bento_pb2.BENTO_STATE_FAILED:
        raise RuntimeError(handlers.error or "birb bento failed")
    return handlers.manifest

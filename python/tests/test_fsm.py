# tests for good_citizen.fsm: step() drives ONE transition and emits, halting on
# UNSPECIFIED; an undeclared/reserved next state is rejected (containment). Parity with
# the Go harness.
from bento.v1 import bento_pb2
from good_citizen import fsm


class _H(fsm.Handlers):
    def on_noticed(self, b):
        return bento_pb2.BENTO_STATE_COOK

    def on_cook(self, b):
        return bento_pb2.BENTO_STATE_DONE

    def on_partial(self, b):
        return bento_pb2.BENTO_STATE_DONE

    def on_done(self, b):
        return bento_pb2.BENTO_STATE_UNSPECIFIED

    def on_failed(self, b):
        return bento_pb2.BENTO_STATE_UNSPECIFIED


def test_step_drives_one_transition_and_emits():
    # one step at a time (the bus loop, mocked): NOTICED -> COOK -> DONE -> terminal.
    emitted = []
    b = bento_pb2.Bento(state=bento_pb2.BENTO_STATE_NOTICED)
    h = _H()
    for _ in range(10):
        prev = b.state
        fsm.step(h, lambda bb, st: emitted.append(st), b)
        if b.state == prev:
            break
    assert emitted == [bento_pb2.BENTO_STATE_COOK, bento_pb2.BENTO_STATE_DONE]
    assert b.state == bento_pb2.BENTO_STATE_DONE


def test_step_rejects_undeclared_state():
    class _Bad(_H):
        def on_noticed(self, b):
            return bento_pb2.BENTO_STATE_CHEW  # reserved / unwired

    b = bento_pb2.Bento(state=bento_pb2.BENTO_STATE_NOTICED)
    try:
        fsm.step(_Bad(), None, b)
        raise AssertionError("reserved state was not rejected")
    except ValueError:
        pass

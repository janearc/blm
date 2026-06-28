# tests for birblib.dispatch: probe in order, run the first available backend, fall
# through on a RUNTIME failure (never fabricate), and return the full decision tree.
import pytest

from birblib.dispatch import Backend, NoBackendAvailable, dispatch


class _Backend:
    # a test backend: declare its name, whether it is available (with a reason), and what
    # run() does (a value to return, or an exception to raise).
    def __init__(self, name, ok, reason, result=None, boom=None):
        self.name = name
        self._ok, self._reason = ok, reason
        self._result, self._boom = result, boom

    def available(self):
        return self._ok, self._reason

    def run(self, *args, **kwargs):
        if self._boom is not None:
            raise self._boom
        return self._result


def test_runs_the_first_available_in_order():
    a = _Backend("a", False, "down")
    b = _Backend("b", True, "up", result="from-b")
    c = _Backend("c", True, "up", result="from-c")
    out, detail = dispatch([a, b, c])
    assert out == "from-b"
    assert detail["backend"] == "b"
    assert detail["tried"] == {"a": "down", "b": "up"}  # c never probed


def test_prefer_jumps_a_backend_to_the_front():
    a = _Backend("a", True, "up", result="from-a")
    b = _Backend("b", True, "up", result="from-b")
    out, detail = dispatch([a, b], prefer="b")
    assert out == "from-b"
    assert detail["backend"] == "b"


def test_unknown_prefer_is_ignored():
    a = _Backend("a", True, "up", result="from-a")
    out, detail = dispatch([a], prefer="nope")
    assert out == "from-a"


def test_runtime_failure_falls_through_and_is_recorded():
    # available but raises -> recorded as "available but failed", fall through, never fake.
    a = _Backend("a", True, "up", boom=RuntimeError("oom"))
    b = _Backend("b", True, "up", result="from-b")
    out, detail = dispatch([a, b])
    assert out == "from-b"
    assert "available but failed: oom" in detail["tried"]["a"]
    assert detail["backend"] == "b"


def test_none_available_raises_with_the_decision_tree():
    a = _Backend("a", False, "down")
    b = _Backend("b", False, "not pulled")
    with pytest.raises(NoBackendAvailable) as ei:
        dispatch([a, b])
    assert ei.value.detail == {"backend": None, "tried": {"a": "down", "b": "not pulled"}}
    assert "a (down)" in str(ei.value) and "b (not pulled)" in str(ei.value)


def test_empty_backend_set_raises_with_none_probed_message():
    # the dead-`or` regression: an empty set must not yield a bare trailing-colon message.
    with pytest.raises(NoBackendAvailable) as ei:
        dispatch([])
    assert ei.value.detail == {"backend": None, "tried": {}}
    assert str(ei.value) == "no backend available: <none probed>"


def test_run_forwards_args_and_kwargs():
    seen = {}

    class _Echo:
        name = "echo"

        def available(self):
            return True, "up"

        def run(self, x, y=0):
            seen["x"], seen["y"] = x, y
            return x + y

    out, _ = dispatch([_Echo()], 3, y=4)
    assert out == 7
    assert seen == {"x": 3, "y": 4}


def test_test_backend_satisfies_the_protocol():
    assert isinstance(_Backend("a", True, "up"), Backend)

# tests for frood.watcher: it is now a thin consumer of a Provider -- it pulls
# sources from provider.read and never touches the filesystem itself. one bad source must
# not abort the pass.
from frood import watcher
from frood.provider import Source


class MockProvider:
    # an in-memory provider: read() yields preset sources, write()/notify() record calls.
    # the watcher must drive entirely through this -- no filesystem access of its own.
    def __init__(self, sources):
        self._sources = list(sources)
        self.writes = []
        self.notifies = []

    def read(self):
        # one pass yields the queued sources, then nothing (as a real provider dedups).
        out, self._sources = self._sources, []
        return out

    def write(self, location, data):
        self.writes.append((location, data))
        return location

    def notify(self, record):
        self.notifies.append(record)


def _src(name):
    return Source(id=name, name=name, location=f"/inbox/{name}")


def test_scan_pulls_sources_from_the_provider():
    provider = MockProvider([_src("a.m4a"), _src("b.wav")])
    handled = []
    out = watcher.scan_once(provider, handled.append)
    assert {s.name for s in out} == {"a.m4a", "b.wav"}
    assert {s.name for s in handled} == {"a.m4a", "b.wav"}


def test_one_bad_source_does_not_stop_the_rest():
    provider = MockProvider([_src("good1"), _src("bad"), _src("good2")])
    ok = []

    def handler(s):
        if s.name == "bad":
            raise RuntimeError("boom")
        ok.append(s.name)

    handled = watcher.scan_once(provider, handler)
    assert set(ok) == {"good1", "good2"}
    assert {s.name for s in handled} == {"good1", "good2"}


def test_watcher_makes_no_direct_filesystem_calls():
    # the seam holds: the watcher module imports neither os nor pathlib -- intake is wholly
    # the provider's job. (a behavioral proof is in test_scan_*, this guards the structure.)
    src = watcher.__dict__
    assert "os" not in src and "Path" not in src
    import inspect

    text = inspect.getsource(watcher)
    assert "open(" not in text and "iterdir" not in text and "Path(" not in text

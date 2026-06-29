# the never-silent-output invariant: no code path reaches a terminal bento without BOTH a
# manifest written at the sink AND a provider.notify -- on DONE, on FAILED, and on a
# zero-artifact reject alike. a run that produced no artifact (input rejected, empty result)
# is a first-class VISIBLE non-success, never a silent DONE.
import json

import pytest

from birblib import driver, service
from birblib.bento import BirbBento
from birblib.handlers import BirbHandlers, CookResult
from frood.provider import FilesystemProvider


class RecordingProvider(FilesystemProvider):
    # a real filesystem provider that ALSO records every write + notify, so a test can
    # assert the never-silent invariant without parsing logs.
    def __init__(self, **kw):
        super().__init__(**kw)
        self.writes = []
        self.notifies = []

    def write(self, location, data):
        self.writes.append(location)
        return super().write(location, data)

    def notify(self, record):
        self.notifies.append(record)
        super().notify(record)


class _Birb(BirbHandlers):
    kind = "test.ingest"
    source_banchan = "src"
    artifact_banchan = "out"

    def __init__(self, *, artifact="result", reject=False, raises=False):
        super().__init__()
        self._artifact, self._reject, self._raises = artifact, reject, raises

    def cook(self, b):
        if self._raises:
            raise RuntimeError("cook exploded")
        if self._reject:
            # the model/content-filter rejected the input: NO artifact, with a reason.
            return CookResult(artifact=None, ok=False, detail={"reason": "rejected by filter"})
        bento = BirbBento(b)
        out = bento.out_dir / "result.txt"
        self.io.write(str(out), "cooked")
        return CookResult(artifact=str(out), ok=True)


def _bento(tmp_path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"bytes")
    return BirbBento.new(
        kind=_Birb.kind, bentos_root=tmp_path / "bentos", name="a.txt",
        banchans=[("src", "source", src)],
    )


def _run(handlers, bento, tmp_path):
    handlers.io = RecordingProvider(notify_dir=tmp_path / "notifications")
    return service.drive(handlers, bento), handlers.io


def _manifest_path(manifest, tmp_path):
    return tmp_path / "bentos" / manifest.bento_id / "manifest.json"


def test_no_artifact_outcome_is_visible(tmp_path):
    # a cook that returns no artifact -> terminal with a manifest at the sink (ok=False,
    # reason in detail) AND notify fired. NOT a silent DONE.
    manifest, io = _run(_Birb(reject=True), _bento(tmp_path), tmp_path)
    assert manifest.ok is False
    assert manifest.state == "FAILED"
    assert manifest.state != "DONE", "a no-artifact run must never be a silent DONE"
    assert manifest.detail["reason"] == "rejected by filter"
    assert manifest.artifact is None
    # the manifest is at the expected sink, and notify fired exactly once.
    on_disk = json.loads(_manifest_path(manifest, tmp_path).read_text())
    assert on_disk["ok"] is False
    assert len(io.notifies) == 1 and io.notifies[0]["ok"] is False


def test_failed_cook_writes_manifest_and_notifies(tmp_path):
    manifest, io = _run(_Birb(raises=True), _bento(tmp_path), tmp_path)
    assert manifest.state == "FAILED" and manifest.ok is False
    assert "cook exploded" in manifest.detail["error"]
    assert _manifest_path(manifest, tmp_path).is_file()
    assert len(io.notifies) == 1

def test_no_source_failed_writes_manifest_and_notifies(tmp_path):
    bento = BirbBento.new(
        kind=_Birb.kind, bentos_root=tmp_path / "bentos", name="gone.txt",
        banchans=[("src", "source", tmp_path / "missing.txt")],
    )
    manifest, io = _run(_Birb(), bento, tmp_path)
    assert manifest.state == "FAILED"
    assert _manifest_path(manifest, tmp_path).is_file()
    assert len(io.notifies) == 1


def test_clean_done_also_notifies(tmp_path):
    # the happy path notifies too -- every terminal announces.
    manifest, io = _run(_Birb(), _bento(tmp_path), tmp_path)
    assert manifest.ok is True and manifest.state == "DONE"
    assert len(io.notifies) == 1 and io.notifies[0]["ok"] is True


def test_cli_path_raises_on_failed_but_daemon_path_returns(tmp_path):
    # C9 regression: cook raising -> FAILED; driver.run (CLI) raises, service.drive (daemon)
    # returns the FAILED manifest so the loop stays up.
    h1 = _Birb(raises=True)
    h1.io = RecordingProvider()
    with pytest.raises(RuntimeError, match="cook exploded"):
        driver.run(h1, _bento(tmp_path))

    h2 = _Birb(raises=True)
    h2.io = RecordingProvider()
    manifest = service.drive(h2, _bento(tmp_path))
    assert manifest.state == "FAILED" and manifest.ok is False


def test_every_terminal_path_finalizes_grep_proof():
    # _finalize is the ONE writer of the manifest + the ONE caller of notify; assert no
    # other method in BirbHandlers writes a manifest or notifies behind its back.
    import inspect

    src = inspect.getsource(BirbHandlers)
    assert src.count("write_manifest(") == 1
    assert src.count(".notify(") == 1
    # both live in _finalize.
    finalize = inspect.getsource(BirbHandlers._finalize)
    assert "write_manifest(" in finalize and ".notify(" in finalize

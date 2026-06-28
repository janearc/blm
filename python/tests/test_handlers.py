# tests for birblib.handlers: the lifecycle skeleton drives NOTICED -> COOK -> (DONE |
# PARTIAL -> DONE | FAILED), copies the source in (dup-over-loss), and persists the
# manifest. a birb implements only cook() -- these pin that the skeleton does the rest.
import json

import pytest
from bento.v1 import bento_pb2

from birblib import driver
from birblib.bento import BirbBento
from birblib.handlers import BirbHandlers, CookResult


class _Birb(BirbHandlers):
    # a minimal birb: a source file in, a text artifact out. flags let a test pick the
    # clean / degraded / failed path without a real model.
    kind = "test.ingest"
    source_banchan = "src"
    artifact_banchan = "out"

    def __init__(self, *, fail=False, degrade=False):
        super().__init__()
        self._fail, self._degrade = fail, degrade

    def cook(self, b):
        if self._fail:
            raise RuntimeError("whisper exploded")
        bento = BirbBento(b)
        out = bento.out_dir / "result.txt"
        out.write_text("cooked from " + bento.banchan("src").location)
        return CookResult(
            artifact=str(out), ok=not self._degrade, detail={"degraded": self._degrade}
        )


def _bento(tmp_path, src_name="a memo.txt"):
    src = tmp_path / src_name
    src.write_bytes(b"real bytes on disk")
    return src, BirbBento.new(
        kind=_Birb.kind,
        bentos_root=tmp_path / "bentos",
        name="a-memo.txt",
        banchans=[("src", "source", src)],
    )


def test_clean_run_walks_cook_then_done(tmp_path):
    src, bento = _bento(tmp_path)
    seen = []
    manifest = driver.run(_Birb(), bento, emitter=lambda b, s: seen.append(s))
    assert seen == [bento_pb2.BENTO_STATE_COOK, bento_pb2.BENTO_STATE_DONE]
    assert manifest.ok is True
    assert manifest.state == "DONE"
    assert manifest.kind == "test.ingest"


def test_noticed_copies_source_and_does_not_move_it(tmp_path):
    # dup-over-loss: the operator's original must still exist, and the banchan repoints
    # at the archived copy under the bento's raw_data.
    src, bento = _bento(tmp_path)
    manifest = driver.run(_Birb(), bento)
    assert src.exists(), "on_noticed must COPY the source, never move/delete it"
    archived = bento.banchan("src").location
    assert "raw_data" in archived
    # the base now archives a request.json at NOTICED (the prompt is the default request).
    assert manifest.params == {"prompt": ""}


def test_artifact_banchan_is_recorded_and_lands_in_manifest(tmp_path):
    src, bento = _bento(tmp_path)
    manifest = driver.run(_Birb(), bento)
    out = bento.banchan("out")
    assert out is not None
    assert manifest.artifact == out.location
    # the manifest is persisted on disk next to the outputs, matching the returned one.
    on_disk = json.loads(bento.manifest_path.read_text())
    assert on_disk["ok"] is True
    assert on_disk["artifact"] == out.location


def test_degraded_cook_is_partial_then_accepted_done(tmp_path):
    # a degraded result is PARTIAL, then on_partial accepts it as DONE (raw beats nothing);
    # the manifest ends DONE/ok with the degrade recorded in detail.
    src, bento = _bento(tmp_path)
    seen = []
    manifest = driver.run(_Birb(degrade=True), bento, emitter=lambda b, s: seen.append(s))
    assert seen == [
        bento_pb2.BENTO_STATE_COOK,
        bento_pb2.BENTO_STATE_PARTIAL,
        bento_pb2.BENTO_STATE_DONE,
    ]
    assert manifest.ok is True
    assert manifest.state == "DONE"
    assert manifest.detail["degraded"] is True


def test_failed_cook_fails_the_bento_and_driver_raises(tmp_path):
    # cook is the step that cannot degrade: a raised exception FAILs the bento and
    # driver.run raises so the cli/daemon surface the error rather than report success.
    src, bento = _bento(tmp_path)
    with pytest.raises(RuntimeError, match="whisper exploded"):
        driver.run(_Birb(fail=True), bento)
    on_disk = json.loads(bento.manifest_path.read_text())
    assert on_disk["ok"] is False
    assert on_disk["state"] == "FAILED"
    assert "whisper exploded" in on_disk["detail"]["error"]


def test_missing_source_fails_at_noticed(tmp_path):
    # no source file -> FAILED at pre-flight, before any cook runs.
    bento = BirbBento.new(
        kind=_Birb.kind,
        bentos_root=tmp_path / "bentos",
        name="gone.txt",
        banchans=[("src", "source", tmp_path / "does-not-exist.txt")],
    )
    with pytest.raises(RuntimeError, match="no source"):
        driver.run(_Birb(), bento)
    assert json.loads(bento.manifest_path.read_text())["state"] == "FAILED"


def test_params_reads_archived_request(tmp_path):
    # a birb declares its resolved request via request(); on_noticed archives it to
    # raw_data/request.json, and params() surfaces it under the manifest.
    src, bento = _bento(tmp_path)

    class _WithRequest(_Birb):
        def request(self, bento):
            return {"prompt": "hi", "recipe": "default"}

    manifest = driver.run(_WithRequest(), bento)
    assert manifest.params == {"prompt": "hi", "recipe": "default"}
    # the archive is real on disk -- replay can reconstruct the intent.
    assert json.loads(bento.request_path.read_text()) == {"prompt": "hi", "recipe": "default"}


def test_source_optional_birb_scaffolds_without_a_copy(tmp_path):
    # a prompt-only birb (no source_banchan) still scaffolds + persists; nothing to copy.
    class _PromptBirb(BirbHandlers):
        kind = "test.generate"
        artifact_banchan = "out"

        def cook(self, b):
            out = BirbBento(b).out_dir / "img.txt"
            out.write_text("rendered")
            return CookResult(artifact=str(out), ok=True)

    bento = BirbBento.new(kind="test.generate", bentos_root=tmp_path / "bentos")
    manifest = driver.run(_PromptBirb(), bento)
    assert manifest.ok is True
    assert bento.bento_path.is_file()  # persisted at NOTICED even with no source

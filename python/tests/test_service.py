# tests for birblib.service: the HTTP job surface (202 submit + poll, never an inline
# render), the artifact traversal guard, and the CLI ACK shape. the heavy work is a fake
# cook, so this exercises the scaffold without a model.
import time
import uuid

import pytest

from birblib import service
from birblib.bento import BirbBento, Manifest
from birblib.handlers import BirbHandlers, CookResult

# fastapi is the optional [service] extra; skip cleanly if it is not installed.
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402 - after the importorskip guard


class _Birb(BirbHandlers):
    kind = "test.generate"
    artifact_banchan = "out"

    def cook(self, b):
        out = BirbBento(b).out_dir / "result.txt"
        out.write_text("rendered: " + b.prompt)
        return CookResult(artifact=str(out), ok=True)


@pytest.fixture
def client(tmp_path):
    bentos_root = tmp_path / "bentos"

    def make_bento(request):
        return BirbBento.new(
            kind=_Birb.kind, bentos_root=bentos_root, prompt=request.get("prompt", "")
        )

    app = service.build_app(
        name="testbirb",
        bentos_root=bentos_root,
        make_handlers=_Birb,
        make_bento=make_bento,
    )
    return TestClient(app), bentos_root


def _wait_for_manifest(bentos_root, bento_id, tries=50):
    # the work runs on a background thread; poll the on-disk manifest briefly.
    for _ in range(tries):
        if service.read_manifest(bentos_root, bento_id) is not None:
            return
        time.sleep(0.02)


def test_health(client):
    c, _ = client
    assert c.get("/health").json() == {"status": "ok", "service": "testbirb"}


def test_submit_returns_202_with_a_job_id(client):
    c, _ = client
    r = c.post("/jobs", json={"prompt": "a cat"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    assert body["bento_id"]
    assert body["job"] == f"/jobs/{body['bento_id']}"


def test_poll_reports_done_with_the_manifest(client):
    c, bentos_root = client
    bento_id = c.post("/jobs", json={"prompt": "a cat"}).json()["bento_id"]
    _wait_for_manifest(bentos_root, bento_id)
    body = c.get(f"/jobs/{bento_id}").json()
    assert body["status"] == "done"
    assert body["manifest"]["ok"] is True
    assert body["manifest"]["kind"] == "test.generate"


def test_poll_unknown_job_is_404(client):
    c, _ = client
    assert c.get("/jobs/nope").status_code == 404


def test_artifact_is_served_after_the_job_finishes(client):
    c, bentos_root = client
    bento_id = c.post("/jobs", json={"prompt": "hello"}).json()["bento_id"]
    _wait_for_manifest(bentos_root, bento_id)
    r = c.get(f"/artifacts/{bento_id}/result.txt")
    assert r.status_code == 200
    assert r.text == "rendered: hello"


def test_artifact_traversal_is_blocked(client):
    c, bentos_root = client
    bento_id = c.post("/jobs", json={"prompt": "x"}).json()["bento_id"]
    _wait_for_manifest(bentos_root, bento_id)
    # a crafted name that climbs out of outputs/ must not be served.
    r = c.get(f"/artifacts/{bento_id}/../../../../etc/hosts")
    assert r.status_code == 404


def test_safe_artifact_path_guard(tmp_path):
    # the guard in isolation: a name inside outputs resolves; one that escapes is rejected.
    # the bento_id must be uuid-shaped (the L2.1 id guard), so use a real one.
    bid = str(uuid.uuid4())
    inside = service._safe_artifact_path(tmp_path, bid, "result.txt")
    assert inside is not None and inside.name == "result.txt"
    assert service._safe_artifact_path(tmp_path, bid, "../../escape") is None


def test_drive_returns_manifest_and_does_not_raise_on_failed(tmp_path):
    # the daemon path: drive() returns the manifest even for a FAILED bento (a daemon logs
    # and stays up), unlike driver.run which raises for the CLI.
    class _Fails(BirbHandlers):
        kind = "test.fail"

        def cook(self, b):
            raise RuntimeError("boom")

    bento = BirbBento.new(kind="test.fail", bentos_root=tmp_path / "bentos")
    manifest = service.drive(_Fails(), bento)
    assert manifest.state == "FAILED"
    assert manifest.ok is False


def _manifest(**kw):
    base = dict(
        bento_id="abc", kind="k", ok=True, state="DONE", artifact="/x/out.txt",
        params={}, stats={}, detail={},
    )
    base.update(kw)
    return Manifest(**base)


def test_ack_shape():
    assert service.ack(_manifest(), message="graaaak") == {
        "status": "ok",
        "bento_id": "abc",
        "state": "DONE",
        "artifact": "/x/out.txt",
        "message": "graaaak",
    }
    assert service.ack(_manifest(ok=False, state="PARTIAL"))["status"] == "incomplete"


def test_serve_inbox_builds_and_drives(tmp_path, monkeypatch):
    # serve_inbox wires frood.watcher to a build-bento-and-drive handler over a
    # provider. drive the watcher one pass (monkeypatch watch -> a single scan) and assert
    # the source was cooked.
    from frood import watcher
    from frood.provider import FilesystemProvider

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.txt").write_text("payload")
    bentos_root = tmp_path / "bentos"

    class _IngestBirb(BirbHandlers):
        kind = "test.ingest"
        source_banchan = "src"
        artifact_banchan = "out"

        def cook(self, b):
            out = BirbBento(b).out_dir / "done.txt"
            self.io.write(str(out), "cooked")
            return CookResult(artifact=str(out), ok=True)

    def make_bento(source):
        return BirbBento.new(
            kind="test.ingest", bentos_root=bentos_root, name=source.name,
            banchans=[("src", "source", source.location)],
        )

    provider = FilesystemProvider(
        inbox, suffixes={".txt"}, debounce_s=0, state_path=tmp_path / "state.json",
    )
    handled = []
    monkeypatch.setattr(
        watcher, "watch",
        lambda p, handler, interval=5.0: handled.append(watcher.scan_once(p, handler)),
    )
    service.serve_inbox(provider, _IngestBirb, make_bento)
    assert handled and handled[0]  # the source was handled
    # a bento was produced with a DONE manifest.
    bentos = [d for d in bentos_root.iterdir() if d.is_dir()]
    assert len(bentos) == 1
    assert service.read_manifest(bentos_root, bentos[0].name).ok is True

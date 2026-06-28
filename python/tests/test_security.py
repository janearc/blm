# tests for the landing-round hardening: the uuid-shape guard on bento_id (no read escape)
# and the PII scrub on error strings (no absolute home paths on the manifest / bus / HTTP).
import uuid
from pathlib import Path

from birblib import service
from birblib.bento import BirbBento
from birblib.handlers import BirbHandlers, _scrub
from good_citizen.provider import FilesystemProvider


# --- L2.1: bento_id shape guard ----------------------------------------------

def test_valid_bento_id():
    assert service._valid_bento_id(str(uuid.uuid4()))
    assert not service._valid_bento_id("..")
    assert not service._valid_bento_id("../etc/passwd")
    assert not service._valid_bento_id("not-a-uuid")
    assert not service._valid_bento_id("")


def test_read_manifest_rejects_crafted_id(tmp_path):
    # a crafted id must not escape the bentos root on a read.
    assert service.read_manifest(tmp_path, "..") is None
    assert service.read_manifest(tmp_path, "../etc") is None


def test_safe_artifact_path_rejects_crafted_id(tmp_path):
    assert service._safe_artifact_path(tmp_path, "../../etc", "x.txt") is None
    # a well-formed id still resolves under outputs.
    good = str(uuid.uuid4())
    p = service._safe_artifact_path(tmp_path, good, "out.txt")
    assert p is not None and p.name == "out.txt"


# --- L2.2: PII scrub on errors -----------------------------------------------

def test_scrub_strips_home_path():
    msg = f"cook failed: {Path.home()}/var/magpie/secret.m4a not found"
    out = _scrub(msg)
    assert str(Path.home()) not in out
    assert out.startswith("cook failed: ~/var/magpie")


def test_error_in_manifest_and_event_is_scrubbed(tmp_path):
    # an error carrying an absolute home path lands scrubbed in detail.error (which feeds the
    # bus error_message and the HTTP surface).
    class _Boom(BirbHandlers):
        kind = "k"

        def cook(self, b):
            raise RuntimeError(f"{Path.home()}/leak.txt could not be read")

    h = _Boom()
    h.io = FilesystemProvider()
    bento = BirbBento.new(kind="k", bentos_root=tmp_path / "bentos")
    manifest = service.drive(h, bento)
    assert manifest.state == "FAILED"
    assert str(Path.home()) not in manifest.detail["error"]
    assert "~/leak.txt" in manifest.detail["error"]

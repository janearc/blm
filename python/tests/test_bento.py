# tests for birblib.bento: BirbBento composes paths in one place, reaches banchans by
# name, persists the bento as the on-disk SOT, and emits the one canonical manifest shape.
import json

from bento.v1 import bento_pb2

from birblib.bento import BirbBento, Manifest, state_name
from frood.provider import FilesystemProvider

# writes route through a provider now; the filesystem one is the default everywhere.
_IO = FilesystemProvider()


def _new(tmp_path, **kw):
    return BirbBento.new(kind="test.kind", bentos_root=tmp_path / "bentos", **kw)


def test_paths_compose_under_root(tmp_path):
    # every path derives from root_path; the layout is the wrapper's business.
    b = _new(tmp_path, name="memo.txt")
    root = b.root
    assert b.raw_dir == root / "raw_data"
    assert b.out_dir == root / "outputs"
    assert b.manifest_path == root / "manifest.json"
    assert b.bento_path == root / "bento.json"
    assert b.request_path == root / "raw_data" / "request.json"
    # the root is bentos_root/<id>, so separate runs never collide.
    assert root.parent == tmp_path / "bentos"
    assert root.name == b.pb.id


def test_new_seeds_a_noticed_bento_with_banchans(tmp_path):
    b = _new(tmp_path, name="x", prompt="names: Will", banchans=[("src", "source", "/tmp/x")])
    assert b.pb.state == bento_pb2.BENTO_STATE_NOTICED
    assert b.pb.kind == "test.kind"
    assert b.pb.prompt == "names: Will"
    assert b.banchan("src").location == "/tmp/x"
    assert b.banchan("missing") is None


def test_add_is_idempotent_repoint_not_duplicate(tmp_path):
    # re-handling on the bus must be idempotent: add() of an existing name repoints it.
    b = _new(tmp_path)
    first = b.add("out", "output", "/a")
    again = b.add("out", "output", "/b")
    assert first.guid == again.guid
    assert again.location == "/b"
    assert sum(1 for ban in b.pb.banchans if ban.name == "out") == 1


def test_scaffold_is_idempotent(tmp_path):
    b = _new(tmp_path)
    b.scaffold()
    b.scaffold()
    assert b.raw_dir.is_dir() and b.out_dir.is_dir()


def test_persist_writes_bento_protojson(tmp_path):
    # the on-disk SOT: the bento itself, as protojson, recoverable without the bus.
    b = _new(tmp_path, name="memo", banchans=[("src", "source", "/tmp/x")])
    b.scaffold()
    b.persist(_IO)
    on_disk = json.loads(b.bento_path.read_text())
    assert on_disk["id"] == b.pb.id
    assert on_disk["kind"] == "test.kind"


def test_write_request_archives_resolved_request(tmp_path):
    b = _new(tmp_path)
    b.write_request({"prompt": "a cat", "recipe": "ambient"}, _IO)
    assert json.loads(b.request_path.read_text())["recipe"] == "ambient"


def test_manifest_envelope_is_the_canonical_shape(tmp_path):
    # the §3.2 envelope: ok is the single success signal, state keeps the distinction,
    # detail is namespaced, artifact is the primary output's location.
    b = _new(tmp_path)
    m = b.manifest(
        state=bento_pb2.BENTO_STATE_DONE,
        artifact="/out/result.txt",
        params={"prompt": "x"},
        stats={"cook": {"wall_s": 1.0}},
        detail={"backend": "afm"},
    )
    assert isinstance(m, Manifest)
    assert m.ok is True
    assert m.to_dict() == {
        "bento_id": b.pb.id,
        "kind": "test.kind",
        "ok": True,
        "state": "DONE",
        "artifact": "/out/result.txt",
        "params": {"prompt": "x"},
        "stats": {"cook": {"wall_s": 1.0}},
        "detail": {"backend": "afm"},
    }
    # the typed boundary round-trips through disk (read parses back into the model).
    assert Manifest.from_dict(m.to_dict()) == m


def test_manifest_ok_is_only_true_for_done(tmp_path):
    b = _new(tmp_path)
    for state in (
        bento_pb2.BENTO_STATE_PARTIAL,
        bento_pb2.BENTO_STATE_FAILED,
        bento_pb2.BENTO_STATE_COOK,
    ):
        m = b.manifest(state=state, artifact=None, params={}, stats={}, detail={})
        assert m.ok is False


def test_state_name_strips_the_prefix():
    assert state_name(bento_pb2.BENTO_STATE_DONE) == "DONE"
    assert state_name(bento_pb2.BENTO_STATE_PARTIAL) == "PARTIAL"
    assert state_name(bento_pb2.BENTO_STATE_FAILED) == "FAILED"

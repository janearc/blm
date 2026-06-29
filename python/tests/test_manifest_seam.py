# tests for the mesh-promotable manifest seam (B2) + the atomic-write safety (B1/C5).
#
# the manifest is a frozen dataclass today (a derived, non-wire view), but it is shaped so
# its on-disk protojson loads straight into the additive BentoManifest proto message -- the
# marked promotion target -- WITHOUT a migration. These pin that seam so it cannot silently
# rot, and that a torn read never throws.
import dataclasses
import json

from google.protobuf import json_format

from bento.v1 import bento_pb2
from birblib import service
from birblib.bento import BirbBento, Manifest


def test_bentomanifest_and_manifest_fieldsets_are_lockstep():
    # L2.3: the dataclass and the proto message MUST carry the same field set, so a later
    # rename on one side fails loudly here instead of silently breaking the promotion seam.
    dataclass_fields = {f.name for f in dataclasses.fields(Manifest)}
    proto_fields = {f.name for f in bento_pb2.BentoManifest.DESCRIPTOR.fields}
    assert dataclass_fields == proto_fields


def _manifest(**kw):
    base = dict(
        bento_id="abc", kind="audio.ingest", ok=True, state="DONE",
        artifact="/var/x/outputs/transcript.txt",
        params={"prompt": "names: Will"}, stats={"transcribe": {"wall_s": 4.1}},
        detail={"degraded": False},
    )
    base.update(kw)
    return Manifest(**base)


def test_manifest_ondisk_is_protojson_loadable():
    # C6: the manifest's on-disk JSON parses as the field set/naming a BentoManifest
    # protojson accepts -- the seam that lets the on-disk shape promote to the wire later.
    on_disk = json.dumps(_manifest().to_dict())
    msg = bento_pb2.BentoManifest()
    json_format.Parse(on_disk, msg)  # raises if the shape/names drift
    assert msg.bento_id == "abc"
    assert msg.kind == "audio.ingest"
    assert msg.ok is True
    assert msg.state == "DONE"
    assert msg.artifact.endswith("transcript.txt")
    # the free-form fields land in the Struct fields.
    assert msg.params["prompt"] == "names: Will"
    assert msg.detail["degraded"] is False


def test_manifest_with_no_artifact_is_protojson_loadable():
    # a zero-artifact (rejected) manifest has artifact=None -> JSON null; protojson maps
    # null to the field default, so it still loads.
    on_disk = json.dumps(_manifest(ok=False, state="FAILED", artifact=None).to_dict())
    msg = bento_pb2.BentoManifest()
    json_format.Parse(on_disk, msg)
    assert msg.ok is False and msg.state == "FAILED"
    assert msg.artifact == ""


def test_manifest_roundtrip_through_bentomanifest_guards_the_seam():
    # dataclass -> on-disk JSON -> BentoManifest -> back: the scalar identity survives. This
    # is the guard that fails loudly the day the dataclass and the proto drift apart.
    m = _manifest()
    msg = bento_pb2.BentoManifest()
    json_format.Parse(json.dumps(m.to_dict()), msg)
    back = json_format.MessageToDict(msg, preserving_proto_field_name=True)
    assert back["bento_id"] == m.bento_id
    assert back["kind"] == m.kind
    assert back["ok"] == m.ok
    assert back["state"] == m.state
    assert set(back).issubset(set(m.to_dict()))  # no field the dataclass lacks


def test_from_dict_tolerates_older_and_unknown_fields():
    # C7: a dict missing newer fields and carrying a legacy/unknown key loads -- missing
    # falls to a default, unknown is ignored, no KeyError.
    older = {"bento_id": "z", "kind": "k", "ok": True, "state": "DONE",
             "legacy_field": "ignore me"}  # no artifact/params/stats/detail; an extra key
    m = Manifest.from_dict(older)
    assert m.bento_id == "z"
    assert m.artifact is None
    assert m.params == {} and m.stats == {} and m.detail == {}
    assert not hasattr(m, "legacy_field")


def test_read_manifest_during_write_is_safe(tmp_path):
    # C5: a truncated manifest (a torn read) yields None, never a JSONDecodeError; a full
    # atomic write leaves no .tmp behind and reads back cleanly.
    bento = BirbBento.new(kind="k", bentos_root=tmp_path / "bentos")
    bento.scaffold()
    # simulate a torn file in place of the manifest.
    bento.manifest_path.write_text('{"bento_id": "z", "ok": tr')  # truncated JSON
    assert service.read_manifest(tmp_path / "bentos", bento.pb.id) is None

    # a real atomic write (through the provider) replaces it cleanly, no .tmp leftover.
    from frood.provider import FilesystemProvider
    bento.write_manifest(_manifest(bento_id=bento.pb.id), FilesystemProvider())
    got = service.read_manifest(tmp_path / "bentos", bento.pb.id)
    assert got is not None and got.bento_id == bento.pb.id
    assert not list(bento.root.glob(".*tmp*"))

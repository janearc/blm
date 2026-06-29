# birblib.bento -- BirbBento, the behavior-bearing wrapper over a bento_pb2.Bento.
#
# generalizes magpie's AudioBento. it owns, in ONE place, the things every birb was
# re-improvising around a raw protobuf: PATH composition under root_path (the layout
# lives here, changes here, never `root / "raw_data"` inline in a handler); BANCHAN
# access by name (asked for through methods, never matched by a bare string); idempotent
# scaffold(); and on-disk PERSISTENCE of the bento itself (the gap the magpie PR left --
# it persisted only a derived manifest, so the bento was lost on the local path).
#
# a birb does not subclass this for behavior -- it declares its kind and banchans and
# lets BirbHandlers drive. a birb MAY subclass to add typed banchan accessors (magpie's
# .audio / .transcript), but the base is complete on its own.

import dataclasses
import json
import uuid
from pathlib import Path

from google.protobuf import json_format

from bento.v1 import bento_pb2


@dataclasses.dataclass(frozen=True)
class Manifest:
    # the one canonical manifest a birb emits, as a typed record. it is NOT a wire contract
    # (bento.proto is the wire SOT); it is a DERIVED view that crosses the disk + HTTP/CLI
    # edge, so it is a plain frozen dataclass -- the standard's "a typed model for the
    # non-mesh edges" without dragging a validation dep into the core frood surface. the
    # field set is fixed; `ok` is the single success signal and is always `state == DONE`.
    bento_id: str
    kind: str
    ok: bool
    state: str
    artifact: str | None
    params: dict
    stats: dict
    detail: dict

    def to_dict(self) -> dict:
        # the JSON-serializable view, for write_manifest and the HTTP/CLI surfaces.
        return dataclasses.asdict(self)

    # the per-field defaults from_dict falls back to. kept beside the fields so a manifest
    # written by an older/newer birb (a field added or dropped) still loads.
    _DEFAULTS = {
        "bento_id": "", "kind": "", "ok": False, "state": "",
        "artifact": None, "params": {}, "stats": {}, "detail": {},
    }

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        # reconstruct from an on-disk manifest.json (the typed boundary on read). TOLERANT:
        # a field the writer omitted falls to its default, and unknown keys are ignored --
        # so a manifest from a different version round-trips without a KeyError. This is the
        # forward-compat seam that lets the on-disk shape promote to the BentoManifest proto
        # later without a migration.
        return cls(**{name: d.get(name, default) for name, default in cls._DEFAULTS.items()})


def state_name(state: int) -> str:
    # the bare BentoState name (DONE, PARTIAL, FAILED, ...) without the BENTO_STATE_
    # prefix, for the manifest's state field. the prefix is wire noise a reader of a
    # manifest does not want; the enum is the source of truth for the spelling.
    return bento_pb2.BentoState.Name(state).removeprefix("BENTO_STATE_")


class BirbBento:
    # one wrapper, every birb. construct it around a bento_pb2.Bento and ask it for the
    # paths and banchans the handlers need; never reach into the protobuf or compose a
    # path by hand out in a handler.

    def __init__(self, pb: bento_pb2.Bento) -> None:
        self.pb = pb

    @classmethod
    def new(
        cls,
        *,
        kind: str,
        bentos_root: Path,
        name: str = "",
        prompt: str = "",
        schema_json: str = "",
        banchans=(),
    ) -> "BirbBento":
        # a fresh bento in NOTICED, with a uuid id and its root under bentos_root/<id>.
        # `banchans` is an iterable of (name, kind, location) tuples -- the source
        # element(s) the birb starts with; on_noticed copies a source in and repoints it.
        bento_id = str(uuid.uuid4())
        pb = bento_pb2.Bento(
            id=bento_id,
            name=name,
            kind=kind,
            state=bento_pb2.BENTO_STATE_NOTICED,
            root_path=str(Path(bentos_root) / bento_id),
            prompt=prompt,
            schema_json=schema_json,
            banchans=[
                bento_pb2.Banchan(guid=str(uuid.uuid4()), name=n, kind=k, location=str(loc))
                for (n, k, loc) in banchans
            ],
        )
        return cls(pb)

    # --- paths: composed here, and nowhere else -------------------------------
    @property
    def root(self) -> Path:
        return Path(self.pb.root_path)

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw_data"

    @property
    def out_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def bento_path(self) -> Path:
        # the on-disk SOT for the standalone/local path: the bento itself, as protojson.
        return self.root / "bento.json"

    @property
    def request_path(self) -> Path:
        # the resolved request the run was built from (intent + recipe resolution).
        return self.raw_dir / "request.json"

    def scaffold(self) -> None:
        # make the bento's directories (idempotent).
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    # --- banchans: by name, through methods -----------------------------------
    def banchan(self, name: str) -> bento_pb2.Banchan | None:
        # the element named `name`, or None. never a bare-string scan out in a handler.
        for ban in self.pb.banchans:
            if ban.name == name:
                return ban
        return None

    def add(self, name: str, kind: str, location) -> bento_pb2.Banchan:
        # declare a new element (e.g. the output a cook produced) with a fresh guid,
        # and return it. if one by that name already exists, repoint it rather than
        # appending a duplicate -- re-handling on the bus must be idempotent.
        existing = self.banchan(name)
        if existing is not None:
            existing.kind = kind
            existing.location = str(location)
            return existing
        ban = bento_pb2.Banchan(
            guid=str(uuid.uuid4()), name=name, kind=kind, location=str(location)
        )
        self.pb.banchans.append(ban)
        return ban

    # --- persistence (all writes route through the provider, atomically) ------
    def persist(self, io) -> None:
        # write the bento itself to root/bento.json as protojson -- the on-disk SOT for the
        # standalone path. the bus is the SOT in the mesh; this is its local mirror, so a run
        # is recoverable from disk without the bus. the write goes through the provider, so
        # it is atomic (a poll never sees a half-written bento) and the sink is swappable.
        io.write(str(self.bento_path), json_format.MessageToJson(self.pb))

    def write_request(self, request: dict, io) -> None:
        # archive the resolved request the run was built from, next to the source.
        io.write(str(self.request_path), json.dumps(request, indent=2))

    def write_manifest(self, manifest: "Manifest", io) -> None:
        # the manifest is the answer to "where is the result, and did it work" -- written at
        # the sink a consumer expects, so a reader finds it without the bus.
        io.write(str(self.manifest_path), json.dumps(manifest.to_dict(), indent=2))

    # --- the manifest envelope (the one canonical shape, §3.2) -----------------
    def manifest(
        self,
        *,
        state: int,
        artifact: str | None,
        params: dict,
        stats: dict,
        detail: dict,
    ) -> Manifest:
        # the single manifest every birb emits, derived from the bento's terminal state.
        # `ok` is the one success signal (state == DONE); `state` keeps the
        # DONE/PARTIAL/FAILED distinction; `detail` is pipeline-specific and namespaced,
        # never spread across the top level.
        return Manifest(
            bento_id=self.pb.id,
            kind=self.pb.kind,
            ok=state == bento_pb2.BENTO_STATE_DONE,
            state=state_name(state),
            artifact=artifact,
            params=params,
            stats=stats,
            detail=detail,
        )

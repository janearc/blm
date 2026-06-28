# birblib.handlers -- BirbHandlers, the lifecycle skeleton every birb shares.
#
# generalizes magpie's AudioHandlers: the NOTICED -> COOK -> (DONE | PARTIAL -> DONE |
# FAILED) walk, with the dup-over-loss pre-flight, the stage-timed work, and the manifest
# persistence all provided. a birb implements ONE method -- cook() -- and declares its
# kind, its source banchan (the input to dup in), and its artifact banchan (the primary
# output). that is the "less code" win: a birb is declaration plus one function.
#
# the stages a birb runs inside cook() never appear on the wire as states -- the bus sees
# only NOTICED -> COOK -> (DONE | PARTIAL -> DONE | FAILED), exactly as the proto intends.

import dataclasses
import json
import logging
import shutil
from pathlib import Path

from bento.v1 import bento_pb2
from good_citizen import fsm
from good_citizen.provider import FilesystemProvider

from birblib.bento import BirbBento, Manifest

logger = logging.getLogger(__name__)


def _scrub(text) -> str:
    # strip PII / absolute home paths from a message that lands in the manifest's
    # detail.error, the bus event's error_message, and the HTTP surface: replace the user's
    # home dir with "~" so no username leaks. a no-PII posture on the error path.
    return str(text).replace(str(Path.home()), "~")


@dataclasses.dataclass
class CookResult:
    # what a birb's cook() returns. `artifact` is the primary output's location (or None
    # if nothing was produced). `ok` is the birb's own success call: True means a clean
    # result (DONE); False means a degraded-but-usable result (PARTIAL -- raw beats
    # nothing). `detail` is the pipeline-specific record (the dispatcher's decision tree,
    # the degrade reason, ...), landed under the manifest's `detail`.
    artifact: str | None
    ok: bool
    detail: dict = dataclasses.field(default_factory=dict)


class BirbHandlers(fsm.Handlers):
    # the lifecycle skeleton. subclass it, set the class attributes below, and implement
    # cook(); the four lifecycle handlers are provided. one instance per bento -- it
    # carries the run's stats + final manifest. the durable outputs live on disk under
    # root_path, so a future distributed handler reads them from there, not from here.

    # --- a birb declares these ------------------------------------------------
    # the kind a fresh bento is stamped with (namespaced: "audio.ingest", "image.generate").
    kind: str = ""
    # the wrapper class for this birb's bentos (override to add typed accessors).
    bento_cls: type[BirbBento] = BirbBento
    # the input element to dup into the bento at NOTICED (None = no file source, e.g. a
    # prompt-only birb whose request is the whole input).
    source_banchan: str | None = None
    # the primary output element cook() produces; its location is the manifest's artifact.
    artifact_banchan: str | None = None

    def __init__(self) -> None:
        self.stats: dict = {}
        self.detail: dict = {}
        self.manifest: Manifest | None = None
        self.error: str = ""
        # the I/O provider every write + the terminal notify route through. defaults to the
        # filesystem; the daemon injects a configured provider (e.g. one with a notify_dir a
        # phone-synced folder watches). swapping the sink is a provider swap, not a code one.
        self.io = FilesystemProvider()

    # --- the ONE method a birb implements -------------------------------------
    def cook(self, b: bento_pb2.Bento) -> CookResult:
        # do the birb's work and return a CookResult. raise to FAIL the bento (a step
        # that cannot degrade); return ok=False to degrade to PARTIAL. time sub-stages
        # with `birblib.Stage(name, self.stats)`.
        raise NotImplementedError

    def request(self, bento: BirbBento) -> dict:
        # the RESOLVED request the run was built from -- archived to raw_data/request.json
        # at NOTICED so a replay can reconstruct intent (C3). default: the per-bento prompt
        # that biases this kind's model passes. a recipe birb overrides this to return its
        # resolved job (recipe + any caller overrides).
        return {"prompt": bento.pb.prompt}

    def params(self, bento: BirbBento) -> dict:
        # the resolved request that becomes the manifest's `params`: read back the
        # request.json archived at NOTICED. empty only if nothing was archived.
        path = bento.request_path
        if path.is_file():
            return json.loads(path.read_text())
        return {}

    # --- the provided lifecycle walk ------------------------------------------
    def on_noticed(self, b: bento_pb2.Bento) -> int:
        # pre-flight: scaffold the bento dir; if the birb declares a source banchan, COPY
        # the source in (dup-over-loss -- never move/delete the operator's original) and
        # repoint the banchan at the archived copy; a missing source -> FAILED. then
        # persist the bento as the on-disk SOT.
        bento = self.bento_cls(b)
        bento.scaffold()
        if self.source_banchan is not None:
            ban = bento.banchan(self.source_banchan)
            src = Path(ban.location) if ban is not None else None
            if src is None or not src.is_file():
                self.error = _scrub(f"no source for banchan {self.source_banchan!r}: {src}")
                self._finalize(bento, bento_pb2.BENTO_STATE_FAILED)
                return bento_pb2.BENTO_STATE_FAILED
            archived = bento.raw_dir / (b.name or src.name)
            shutil.copy2(src, archived)
            ban.location = str(archived)
        # archive the resolved request (C3) and persist the bento as the on-disk SOT.
        bento.write_request(self.request(bento), self.io)
        bento.persist(self.io)
        return bento_pb2.BENTO_STATE_COOK

    def on_cook(self, b: bento_pb2.Bento) -> int:
        # the work. call cook(); a raised exception is the un-degradable failure (FAILED,
        # and process() raises); ok=False is the degraded outcome (PARTIAL); ok=True is
        # DONE. record the artifact banchan and the detail, then persist the manifest.
        bento = self.bento_cls(b)
        try:
            result = self.cook(b)
        except Exception as e:  # noqa: BLE001 - cook is the step that cannot degrade; any error FAILs
            self.error = _scrub(f"cook failed: {e}")
            logger.error("birblib: %s", self.error)
            self._finalize(bento, bento_pb2.BENTO_STATE_FAILED)
            return bento_pb2.BENTO_STATE_FAILED
        self.detail = dict(result.detail or {})
        if result.artifact is None:
            # never a silent no-output: a run that produced NO artifact (the input was
            # rejected, the result was empty) is a VISIBLE non-success, not a silent DONE.
            # the manifest invariant (ok == state==DONE) means a no-artifact run cannot be
            # DONE, so it terminates FAILED with the reason -- and _finalize still writes the
            # manifest at the sink and notifies. (BENTO_STATE_SPOILED is the natural home for
            # "rejected", but it is reserved/unwired in the proto; FAILED is the honest term
            # today. See the open decision in the PR.)
            reason = self.detail.get("reason") or "no artifact produced (input rejected/empty)"
            self.error = _scrub(reason)
            self._finalize(bento, bento_pb2.BENTO_STATE_FAILED)
            return bento_pb2.BENTO_STATE_FAILED
        if self.artifact_banchan:
            bento.add(self.artifact_banchan, kind="output", location=result.artifact)
        state = bento_pb2.BENTO_STATE_DONE if result.ok else bento_pb2.BENTO_STATE_PARTIAL
        self._finalize(bento, state)
        return state

    def on_partial(self, b: bento_pb2.Bento) -> int:
        # the convergence seam. PARTIAL means cook worked but degraded (e.g. a model was
        # down and the raw result was kept). the proto reserves PARTIAL for
        # substrate-owned convergence, which is UNDEFINED today; the honest stopgap is to
        # accept the degraded artifact and finish DONE -- raw beats nothing. this is the
        # documented place that changes when convergence lands; a birb may override.
        bento = self.bento_cls(b)
        self._finalize(bento, bento_pb2.BENTO_STATE_DONE)
        return bento_pb2.BENTO_STATE_DONE

    def on_done(self, b: bento_pb2.Bento) -> int:
        # terminal. outputs + manifest were written before the transition; nothing local.
        return bento_pb2.BENTO_STATE_UNSPECIFIED

    def on_failed(self, b: bento_pb2.Bento) -> int:
        # terminal. the manifest (with error in detail) was written at the failure.
        return bento_pb2.BENTO_STATE_UNSPECIFIED

    # --- manifest assembly, in one place --------------------------------------
    def _finalize(self, bento: BirbBento, state: int) -> None:
        # assemble + persist the manifest for `state`. the error, when set, lands in
        # detail.error -- never as a fabricated artifact.
        artifact = None
        if self.artifact_banchan:
            ban = bento.banchan(self.artifact_banchan)
            artifact = ban.location if ban is not None else None
        detail = dict(self.detail)
        if self.error:
            detail["error"] = self.error
        self.manifest = bento.manifest(
            state=state,
            artifact=artifact,
            params=self.params(bento),
            stats=self.stats,
            detail=detail,
        )
        # never-silent: the ONE place a bento goes terminal writes the manifest at the sink
        # AND notifies -- on DONE, on FAILED, and on a zero-artifact reject alike. no terminal
        # path reaches rest without both. (grep-proof: _finalize is the only manifest writer.)
        bento.write_manifest(self.manifest, self.io)
        self.io.notify(self.manifest.to_dict())

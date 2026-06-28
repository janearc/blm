# birblib.service -- the service scaffold a birb gets for free: the inbox daemon, the
# async-submit HTTP surface, and the CLI ACK shape. the per-modality /v1 facade (images
# vs audio vs video differ) stays the birb's own; the job API, health, and artifact
# serving are the lib's.
#
# fastapi/uvicorn are an OPTIONAL extra (`blm-good-citizen[service]`): they are imported
# lazily inside the HTTP functions, so a birb that only wants the bento/handlers/daemon
# never pays for them. the daemon half rides on good_citizen.watcher (stdlib) and needs no
# extra.

import json
import logging
import threading
import uuid
from pathlib import Path

from good_citizen import watcher
from good_citizen import emit as _emit

from birblib.bento import Manifest
from birblib.driver import _pb, _walk

logger = logging.getLogger(__name__)


def _valid_bento_id(bento_id) -> bool:
    # a bento_id is a uuid4. Validate the SHAPE before it touches a path, so a crafted id
    # ("..", "../x", a separator) cannot escape the bentos root on a read -- the artifact
    # traversal guard covers the name, this covers the id segment.
    try:
        uuid.UUID(str(bento_id))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


# --- driving a bento with the REAL sidecar emit (the daemon/http path) ------------

def drive(handlers, bento, sidecar_url=None) -> Manifest | None:
    # step a bento to a terminal state, relaying each transition to the Go sidecar (the
    # bus). shares the FSM step-loop with driver.run via _walk; unlike driver.run (the CLI,
    # which raises on FAILED so a shell sees the error), this returns the manifest and never
    # raises on a FAILED bento -- a daemon logs the outcome and stays up for the next file.
    # an unexpected exception still propagates so the watcher's per-file guard can catch it.
    pb = _pb(bento)
    # the emitter closes over the handler so a FAILED event carries error_message + trace_id.
    _walk(handlers, pb, _emit.sidecar_emitter(sidecar_url, handlers))
    return handlers.manifest


# --- the inbox daemon -------------------------------------------------------------

def serve_inbox(provider, make_handlers, make_bento, *, sidecar_url=None, interval=5.0) -> None:
    # watch `provider` for new sources; for each, build a bento (make_bento(source) ->
    # BirbBento in NOTICED), wire the SAME provider into the handler (so its writes and the
    # terminal notify land at the configured sink), and drive it to terminal with the real
    # sidecar emit. make_handlers() -> a fresh BirbHandlers per source. dup-over-loss and the
    # persistent, restart-surviving dedup are the provider's job.
    def _handle(source):
        bento = make_bento(source)
        handlers = make_handlers()
        handlers.io = provider
        manifest = drive(handlers, bento, sidecar_url=sidecar_url)
        # record delivery ONLY after the bento reached a terminal state (DONE or FAILED). a
        # crash before this point leaves the source undelivered, so a restart re-delivers it
        # rather than abandoning the work silently (at-least-once).
        provider.mark_done(source)
        if manifest is not None:
            logger.info(
                "birblib: %s -> %s (ok=%s)", source.name, manifest.artifact, manifest.ok,
            )

    watcher.watch(provider, _handle, interval=interval)


# --- the HTTP surface (async submit + poll + artifact serving) --------------------

def read_manifest(bentos_root, bento_id: str) -> Manifest | None:
    # the on-disk manifest for a bento, or None if it has not been written yet (the job is
    # still running) -- the manifest IS the job record on the local path. parsed back into
    # the typed model, so the boundary is typed on read as well as on write. atomic writes
    # mean a reader never sees a torn file; even so, a truncated/partial read is treated as
    # "not yet readable" (None), never a JSONDecodeError surfacing to a poll.
    if not _valid_bento_id(bento_id):
        return None
    path = Path(bentos_root) / bento_id / "manifest.json"
    if not path.is_file():
        return None
    try:
        return Manifest.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, ValueError):
        return None


def _safe_artifact_path(bentos_root, bento_id: str, name: str) -> Path | None:
    # resolve an artifact request to a path UNDER the bento's outputs dir, or None if the
    # name would escape it (the traversal guard). a crafted "../../etc/passwd" resolves
    # outside `base` and is rejected; only a path that stays within outputs is served. the
    # bento_id is shape-checked too, so a crafted id segment cannot escape the root.
    if not _valid_bento_id(bento_id):
        return None
    base = (Path(bentos_root) / bento_id / "outputs").resolve()
    target = (base / name).resolve()
    if base != target and base not in target.parents:
        return None
    return target


def build_app(*, name, bentos_root, make_handlers, make_bento, sidecar_url=None, provider=None):
    # build the birb's HTTP app: /health, 202 submit (POST /jobs) + poll (GET /jobs/{id}),
    # and artifact serving with the traversal guard.
    #
    # SCOPE -- READ THIS: POST /jobs here is a SINGLE-NODE / LOCAL-DEV affordance, NOT the
    # fleet submit path. It persists the NOTICED bento (durable on disk) and then drives it
    # on an in-process background thread; if this instance dies mid-job, the in-flight work
    # is NOT resumed by another instance. That is a pet, and the mesh exists to avoid pets.
    #
    # The FLEET submit path is BUS-ENQUEUE: persist the NOTICED bento, emit its
    # BentoLifecycleEvent(NOTICED), return 202, and do NO in-process work -- a bus worker
    # consuming NOTICED drives the FSM, and a worker death is recovered by redelivery (the
    # same resilience serve_inbox already has via the inbox + idempotent reprocess). When an
    # HTTP-job worker exists, this submit becomes persist-emit-return and the thread is
    # deleted. Until then, use this for local dev only.
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse

    app = FastAPI(title=name)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": name}

    @app.post("/jobs", status_code=202)
    def submit(request: dict):
        # single-node/local-dev (see build_app's banner): persist the NOTICED bento so the
        # record is durable the instant we 202, THEN drive it on a background thread. The
        # fleet path replaces the thread with a NOTICED emit a bus worker consumes.
        bento = make_bento(request)
        bento_id = bento.pb.id
        handlers = make_handlers()
        if provider is not None:
            handlers.io = provider
        bento.scaffold()
        bento.persist(handlers.io)

        def _run():
            try:
                drive(handlers, bento, sidecar_url=sidecar_url)
            except Exception as e:  # noqa: BLE001 - one job's failure must not kill the worker
                logger.error("birblib: job %s crashed: %s", bento_id, e)

        threading.Thread(target=_run, daemon=True).start()
        return {"status": "accepted", "bento_id": bento_id, "job": f"/jobs/{bento_id}"}

    @app.get("/jobs/{bento_id}")
    def job(bento_id: str):
        if not _valid_bento_id(bento_id):
            raise HTTPException(status_code=404, detail="no such job")
        manifest = read_manifest(bentos_root, bento_id)
        if manifest is None:
            if (Path(bentos_root) / bento_id).is_dir():
                return {"status": "running", "bento_id": bento_id}
            raise HTTPException(status_code=404, detail="no such job")
        return {
            "status": "done" if manifest.ok else manifest.state.lower(),
            "manifest": manifest.to_dict(),
        }

    @app.get("/artifacts/{bento_id}/{name:path}")
    def artifact(bento_id: str, name: str):
        path = _safe_artifact_path(bentos_root, bento_id, name)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="no such artifact")
        return FileResponse(path)

    return app


# --- the CLI ACK ------------------------------------------------------------------

def ack(manifest: Manifest, message: str = "") -> dict:
    # the JSON a birb's CLI prints: an ACK of where the result landed, not the bytes. it
    # is json-by-default (a birb is a good agent-citizen) and reports ok + the artifact
    # path, so an agent caller can find the output and know whether it worked.
    out = {
        "status": "ok" if manifest.ok else "incomplete",
        "bento_id": manifest.bento_id,
        "state": manifest.state,
        "artifact": manifest.artifact,
    }
    if message:
        out["message"] = message
    return out

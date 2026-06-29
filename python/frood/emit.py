# frood.emit -- relay a bento lifecycle event to the local Go sidecar, which
# owns the kafka / schema-registry / protobuf wire. Python never touches kafka.
#
# Best-effort: emit() never raises. A sidecar or bus hiccup must not break a bento --
# the bus is the durable record, and a missed emit is recovered by re-handling the
# work, never by failing it. Modeled on paling's daemon emit (stdlib urllib, no deps
# beyond protobuf).
import logging
import os
import urllib.request
import uuid

from google.protobuf import json_format

from bento.v1 import bento_pb2

log = logging.getLogger(__name__)

# the local Go sidecar's intake. Override with FROOD_SIDECAR_URL.
_SIDECAR_URL = os.environ.get("FROOD_SIDECAR_URL", "http://localhost:9090/emit")


def emit(event, sidecar_url=None):
    # POST the event as protojson (the contract's canonical JSON) to the sidecar.
    # Never raises -- a failure is logged and dropped.
    url = sidecar_url or _SIDECAR_URL
    try:
        body = json_format.MessageToJson(event).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=2).close()
    except Exception as e:  # noqa: BLE001 - emit is best-effort; a hiccup must not break the bento
        log.warning("frood: emit to sidecar failed, dropped: %s", e)


def sidecar_emitter(sidecar_url=None, handler=None):
    # build an Emitter for the generated fsm harness: step() calls emitter(b, state) on each
    # transition, and this relays a BentoLifecycleEvent to the sidecar. event_id is a fresh
    # uuid4 (the idempotency key); the bento carries its own id and kind.
    #
    # the failure REASON lives on the HANDLER, not the bento, so the emitter closes over the
    # handler to populate error_message on a FAILED event -- without this, a FAILED bento's
    # bus event carried no error and there was no provenance/correlation. trace_id correlates
    # one bento's processing; the bento has no trace field yet, so trace_id == bento_id for
    # now (a bento's events share its id as the trace until a real trace field lands).
    def _emit(b, state):
        ev = bento_pb2.BentoLifecycleEvent(
            event_id=str(uuid.uuid4()),
            trace_id=b.id,
            bento_id=b.id,
            bento_kind=b.kind,
            state=state,
            handler=type(handler).__name__ if handler is not None else "",
        )
        if state == bento_pb2.BENTO_STATE_FAILED and handler is not None:
            ev.error_message = getattr(handler, "error", "") or ""
        emit(ev, sidecar_url)

    return _emit

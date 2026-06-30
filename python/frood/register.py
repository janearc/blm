# frood.register -- a frood joins delightd's live registry. delightd is the broker and the
# source of truth for who is on the mesh; a frood presents its declared project, identity, the
# contracts it speaks, and the endpoint(s) it has bound, and delightd records it under a lease or
# the registration does not complete.
#
# FAIL LOUD, by design. emit (frood.emit) is best-effort -- the bus is the durable record, so a
# missed emit is recovered by re-handling the work and is never worth failing a bento over.
# Registration is the opposite: a frood that cannot register MUST know it, loudly. delightd is
# the source of truth for membership, and a frood that assumes it joined when it did not is
# exactly the silent degradation the mesh forbids -- it would serve as if trusted while delightd
# has no record of it. So register() raises on any non-completion (a 4xx/5xx from delightd, or an
# unreachable delightd); the caller decides what to do with that (retry, refuse to serve), but it
# is never swallowed here.
import json
import logging
import os
import urllib.error
import urllib.request

from google.protobuf import json_format

from registry.v1 import register_pb2

log = logging.getLogger(__name__)

# delightd's control port. Override with DELIGHTD_URL. 8088 is delightd's DefaultControlPort
# (compose publishes 127.0.0.1:8088; the kube Deployment uses containerPort 8088).
_DELIGHTD_URL = os.environ.get("DELIGHTD_URL", "http://localhost:8088")

# how long to wait on the /register round-trip. delightd runs a /health guarantee against the
# frood's endpoint during the call, so this is a touch longer than a bare request.
_TIMEOUT_SECS = 5


class RegistrationError(Exception):
    # A registration that did not complete. status is delightd's HTTP status (0 when delightd
    # was unreachable); reason is the cause delightd reported (it answers a JSON {"error": ...}
    # body on the never-silent not-registered path), so a caller can log or branch on WHY the
    # join failed -- "unknown_project", "unreachable" endpoint, an unverified contract -- not
    # just that it did.
    #
    # Branch on `status`, not `reason`: status is the STABLE axis (0 == delightd unreachable or
    # timed out; otherwise delightd's HTTP code -- 404 unknown project, 422 validation family,
    # 409 endpoint held, 503 schema registry unavailable, 500 record failure). `reason` is human
    # prose for logs, not a stable machine code -- delightd's stable code strings
    # (unknown_project, endpoint_held, ...) ride the bus NotRegistered event, not this HTTP body.
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason
        super().__init__(f"registration did not complete (HTTP {status}): {reason}")


def build_request(identity, contracts, endpoints):
    # Assemble a registry.v1.RegisterRequest from a frood's identity, the contracts it speaks, and
    # the endpoint(s) it has bound. project is taken from the identity so the two cannot drift --
    # delightd rejects a request whose top-level project disagrees with identity.project, and
    # there is only one source for it here. endpoints is any iterable of registry.v1.Endpoint.
    #
    # There is deliberately NO role/kind field: whether a frood watches or listens is a roster
    # attribute delightd already holds, not something re-declared at register time.
    return register_pb2.RegisterRequest(
        project=identity.project,
        identity=identity,
        contracts=contracts,
        endpoints=list(endpoints),
    )


def register(identity, contracts, endpoints, delightd_url=None):
    # POST a RegisterRequest as protojson to delightd's /register and return the parsed
    # registry.v1.RegisterResponse on success. Raises RegistrationError on any non-2xx (delightd
    # declined the join, and says why) and on an unreachable delightd -- a frood never gets to
    # believe it joined when it did not.
    #
    # register-once: this returns the RegisterResponse (which carries delightd's lease_ttl_seconds)
    # but does NOT renew the lease. Lease renewal / heartbeat-keepalive is intentionally out of
    # scope here -- delightd stamps a TTL but does not enforce expiry yet, so there is nothing to
    # renew against; a caller that later needs renewal drives it on its own cadence.
    req = build_request(identity, contracts, endpoints)
    url = (delightd_url or _DELIGHTD_URL).rstrip("/") + "/register"
    body = json_format.MessageToJson(req).encode()
    http_req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(http_req, timeout=_TIMEOUT_SECS) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        # delightd reports a not-completed registration as an HTTP error with a JSON body; pull
        # the reason out so the failure names WHY, not just the status.
        reason = _reason_from_error_body(e)
        log.warning("frood: registration declined by delightd (HTTP %s): %s", e.code, reason)
        raise RegistrationError(e.code, reason) from e
    except urllib.error.URLError as e:
        # delightd unreachable (DNS, connection refused, a wrapped connect-phase timeout): the
        # frood cannot confirm it joined, so this is a loud failure too (never a silent "assume
        # registered").
        raise RegistrationError(0, f"delightd unreachable: {e.reason}") from e
    except TimeoutError as e:
        # a READ-phase timeout (the response stalled mid-body) raises a bare TimeoutError, not a
        # URLError, so it would otherwise escape the typed handlers above. Catch it explicitly: a
        # frood that timed out waiting on /register does not know whether it joined, so this must
        # surface as the same loud RegistrationError, naming the timeout, not a bare exception the
        # caller has to special-case.
        raise RegistrationError(0, f"delightd timed out after {_TIMEOUT_SECS}s") from e
    return json_format.Parse(raw, register_pb2.RegisterResponse())


def _reason_from_error_body(err):
    # delightd's not-registered body is JSON {"error": "<reason>"}. Best-effort extraction: if the
    # body is missing or not that shape, fall back to the HTTP reason phrase so a parse miss never
    # hides the failure (the exception is raised either way).
    try:
        payload = json.loads(err.read().decode())
    except Exception:  # noqa: BLE001 - a malformed error body must not mask the registration failure
        return err.reason or "unknown error"
    if isinstance(payload, dict):
        return payload.get("error") or payload.get("reason") or err.reason or "unknown error"
    return err.reason or "unknown error"

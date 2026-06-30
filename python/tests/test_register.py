# tests for frood.register: it POSTs a RegisterRequest as protojson, parses the
# RegisterResponse, and -- unlike emit (best-effort) -- FAILS LOUD when delightd declines the
# join or is unreachable. A frood never gets to believe it registered when it did not.
import io
import json
import urllib.error
import urllib.request

import pytest
from google.protobuf import json_format

from frood import register
from frood.v1 import frood_pb2
from registry.v1 import register_pb2


def _identity():
    return frood_pb2.Identity(service_name="magpie", project="magpie", version="1.0.0")


def _contracts():
    c = frood_pb2.ContractDescriptor()
    # every frood MUST emit the heartbeat; the descriptor declares it.
    c.emits.add(subject="observability.v1.ServiceHealthHeartbeat")
    return c


def _endpoints():
    return [register_pb2.Endpoint(scheme="http", address="magpie.fleet:8092")]


class _Resp:
    # a context-manager HTTP response whose read() returns the given bytes (matches the
    # `with urllib.request.urlopen(...) as resp` shape register() uses).
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_build_request_takes_project_from_identity_and_has_no_kind():
    req = register.build_request(_identity(), _contracts(), _endpoints())
    assert req.project == "magpie"
    assert req.identity.service_name == "magpie"
    assert req.endpoints[0].address == "magpie.fleet:8092"
    assert req.contracts.emits[0].subject == "observability.v1.ServiceHealthHeartbeat"
    # there is no role/kind field on the wire -- watcher vs listener is a roster attribute.
    field_names = {f.name for f in register_pb2.RegisterRequest.DESCRIPTOR.fields}
    assert "kind" not in field_names
    assert field_names == {"project", "identity", "contracts", "endpoints"}


def test_register_posts_protojson_and_parses_response(monkeypatch):
    captured = {}
    resp_msg = register_pb2.RegisterResponse(
        identity=_identity(),
        endpoint=register_pb2.Endpoint(scheme="http", address="magpie.fleet:8092"),
        lease_ttl_seconds=30,
    )
    resp_body = json_format.MessageToJson(resp_msg).encode()

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data
        return _Resp(resp_body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = register.register(_identity(), _contracts(), _endpoints(), "http://delightd:8088")

    assert captured["method"] == "POST"
    assert captured["url"] == "http://delightd:8088/register"
    # the request body round-trips back to the RegisterRequest we built.
    sent = register_pb2.RegisterRequest()
    json_format.Parse(captured["body"].decode(), sent)
    assert sent.project == "magpie"
    assert sent.identity.project == "magpie"
    assert sent.endpoints[0].address == "magpie.fleet:8092"
    # the parsed response carries delightd's confirmation.
    assert out.lease_ttl_seconds == 30
    assert out.endpoint.address == "magpie.fleet:8092"


def test_register_fails_loud_on_decline(monkeypatch):
    # delightd declines with an HTTP error + {"error": reason}; register must raise, naming why.
    body = json.dumps({"error": "project not found"}).encode()

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(register.RegistrationError) as ei:
        register.register(_identity(), _contracts(), _endpoints(), "http://delightd:8088")
    assert ei.value.status == 404
    assert ei.value.reason == "project not found"


def test_register_fails_loud_on_unreachable(monkeypatch):
    # delightd unreachable: the frood cannot confirm it joined -> loud failure with status 0.
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(register.RegistrationError) as ei:
        register.register(_identity(), _contracts(), _endpoints())
    assert ei.value.status == 0
    assert "unreachable" in str(ei.value).lower()


def test_register_fails_loud_on_read_timeout(monkeypatch):
    # a read-phase timeout raises a bare TimeoutError (not a URLError); it must still surface as
    # a loud RegistrationError naming the timeout, not a bare exception the caller special-cases.
    def fake_urlopen(req, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(register.RegistrationError) as ei:
        register.register(_identity(), _contracts(), _endpoints())
    assert ei.value.status == 0
    assert "timed out" in str(ei.value).lower()


def test_reason_falls_back_on_malformed_error_body(monkeypatch):
    # a non-JSON error body must not mask the failure -- it still raises, with the HTTP reason.
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 500, "Internal Server Error", {}, io.BytesIO(b"not json")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(register.RegistrationError) as ei:
        register.register(_identity(), _contracts(), _endpoints())
    assert ei.value.status == 500

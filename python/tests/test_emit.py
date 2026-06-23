# tests for good_citizen.emit: it POSTs the event as protojson, is best-effort (never
# raises), and the fsm Emitter builds the right event from (bento, state).
import urllib.request

from google.protobuf import json_format

from bento.v1 import bento_pb2
from good_citizen import emit


def test_emit_posts_protojson(monkeypatch):
    captured = {}

    class _Resp:
        def close(self):
            pass

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["method"] = req.get_method()
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ev = bento_pb2.BentoLifecycleEvent(
        event_id="e1", bento_id="b1", bento_kind="voice-memo", state=bento_pb2.BENTO_STATE_COOK
    )
    emit.emit(ev, "http://localhost:9090/emit")
    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:9090/emit"
    # the body round-trips back to the same event
    back = bento_pb2.BentoLifecycleEvent()
    json_format.Parse(captured["body"].decode(), back)
    assert back.bento_id == "b1"
    assert back.state == bento_pb2.BENTO_STATE_COOK


def test_emit_is_best_effort(monkeypatch):
    # a transport failure must not raise -- emit swallows and logs.
    def boom(req, timeout=None):
        raise OSError("sidecar down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    emit.emit(bento_pb2.BentoLifecycleEvent(event_id="e2", bento_id="b2"), "http://x/emit")


def test_sidecar_emitter_builds_event(monkeypatch):
    # the Emitter the fsm harness calls builds a BentoLifecycleEvent from (bento, state).
    sent = []
    monkeypatch.setattr(emit, "emit", lambda ev, url=None: sent.append(ev))
    em = emit.sidecar_emitter()
    em(bento_pb2.Bento(id="b3", kind="voice-memo"), bento_pb2.BENTO_STATE_DONE)
    assert len(sent) == 1
    assert sent[0].bento_id == "b3"
    assert sent[0].bento_kind == "voice-memo"
    assert sent[0].state == bento_pb2.BENTO_STATE_DONE
    assert sent[0].event_id  # a uuid4 was set

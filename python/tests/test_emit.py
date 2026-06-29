# tests for frood.emit: it POSTs the event as protojson, is best-effort (never
# raises), and the fsm Emitter builds the right event from (bento, state).
import urllib.request

from google.protobuf import json_format

from bento.v1 import bento_pb2
from frood import emit


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
    assert sent[0].trace_id == "b3"  # trace_id == bento_id until a real trace field lands


def test_failed_event_carries_error_and_trace(monkeypatch):
    # the lossy-emit fix: a FAILED event must carry WHY. the error lives on the handler, so
    # the emitter closes over it; trace_id correlates the bento's events.
    sent = []
    monkeypatch.setattr(emit, "emit", lambda ev, url=None: sent.append(ev))

    class _H:
        error = "transcribe failed: whisper exploded"

    em = emit.sidecar_emitter(handler=_H())
    em(bento_pb2.Bento(id="b9", kind="audio.ingest"), bento_pb2.BENTO_STATE_FAILED)
    ev = sent[0]
    assert ev.error_message == "transcribe failed: whisper exploded"
    assert ev.trace_id == "b9"
    assert ev.handler == "_H"


def test_non_failed_event_has_no_error(monkeypatch):
    # error_message is set only on FAILED -- it must not leak onto a healthy transition.
    sent = []
    monkeypatch.setattr(emit, "emit", lambda ev, url=None: sent.append(ev))

    class _H:
        error = "should not appear on a DONE event"

    em = emit.sidecar_emitter(handler=_H())
    em(bento_pb2.Bento(id="b10"), bento_pb2.BENTO_STATE_DONE)
    assert sent[0].error_message == ""
    assert sent[0].trace_id == "b10"

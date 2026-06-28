# tests for good_citizen.provider.FilesystemProvider: persistent dedup that survives a
# restart, the partial-write guard, atomic writes, and the notify drop.
import json
import os
import time
from pathlib import Path

from good_citizen.provider import FilesystemProvider, atomic_write


def _drop(inbox: Path, name: str, data: bytes = b"payload") -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    p = inbox / name
    p.write_bytes(data)
    return p


def test_read_delivers_new_sources(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.txt")
    _drop(inbox, "b.txt")
    provider = FilesystemProvider(inbox, debounce_s=0)
    assert {s.name for s in provider.read()} == {"a.txt", "b.txt"}
    # a second pass in the same process delivers nothing (already delivered).
    assert list(provider.read()) == []


def test_suffix_filter(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.m4a")
    _drop(inbox, "note.txt")
    provider = FilesystemProvider(inbox, suffixes={".m4a"}, debounce_s=0)
    assert {s.name for s in provider.read()} == {"a.m4a"}


def test_dedup_persists_across_restart(tmp_path):
    # deliver a file, then DROP the provider (simulate a reboot) and build a fresh one over
    # the same inbox+state -> the file is NOT re-delivered, and no duplicate work happens.
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.txt")
    first = FilesystemProvider(inbox, debounce_s=0)
    assert {s.name for s in first.read()} == {"a.txt"}

    # "restart": a brand-new provider instance, in-memory state gone, reads the on-disk log.
    restarted = FilesystemProvider(inbox, debounce_s=0)
    assert list(restarted.read()) == [], "a restart must not re-deliver an already-handled file"

    # a GENUINE re-drop (the file's mtime moves to a new, settled time) is a new fact and IS
    # delivered. (a re-copy moves mtime; we use a past time so the stability guard passes.)
    earlier = time.time() - 100
    os.utime(inbox / "a.txt", (earlier, earlier))
    assert {s.name for s in restarted.read()} == {"a.txt"}


def test_skips_file_still_being_written(tmp_path):
    # the partial-write guard: a file whose mtime is within the debounce window is "still
    # being written" and is held until it goes quiet.
    inbox = tmp_path / "inbox"
    p = _drop(inbox, "in-flight.txt")
    provider = FilesystemProvider(inbox, debounce_s=30)
    # fresh mtime -> not yet stable -> skipped.
    assert list(provider.read()) == []
    # quiesce: backdate the mtime past the debounce -> now delivered.
    old = time.time() - 60
    os.utime(p, (old, old))
    assert {s.name for s in provider.read()} == {"in-flight.txt"}


def test_does_not_move_or_delete_the_source(tmp_path):
    inbox = tmp_path / "inbox"
    p = _drop(inbox, "a.txt")
    provider = FilesystemProvider(inbox, debounce_s=0)
    list(provider.read())
    assert p.exists(), "dup-over-loss: the provider must never move or delete the source"


def test_atomic_write_leaves_no_tmp(tmp_path):
    dest = tmp_path / "out" / "result.txt"
    provider = FilesystemProvider()
    loc = provider.write(str(dest), "the bytes")
    assert Path(loc).read_text() == "the bytes"
    # no sibling .tmp left behind.
    assert not list((tmp_path / "out").glob(".*tmp*"))


def test_atomic_write_replaces_in_place(tmp_path):
    dest = tmp_path / "r.txt"
    atomic_write(dest, "v1")
    atomic_write(dest, "v2")
    assert dest.read_text() == "v2"


def test_notify_drops_a_record(tmp_path):
    notify_dir = tmp_path / "notifications"
    provider = FilesystemProvider(notify_dir=notify_dir)
    provider.notify({"bento_id": "abc", "ok": True, "state": "DONE"})
    rec = json.loads((notify_dir / "abc.json").read_text())
    assert rec["ok"] is True and rec["state"] == "DONE"


def test_notify_without_dir_does_not_raise(tmp_path):
    # a provider with no notify_dir still satisfies notify (it logs); it must not blow up.
    FilesystemProvider().notify({"bento_id": "x", "ok": False, "state": "FAILED"})

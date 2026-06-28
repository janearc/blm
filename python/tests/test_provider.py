# tests for good_citizen.provider.FilesystemProvider: terminal-recorded dedup that survives
# a restart and re-delivers on a crash, the partial-write guard, the hardened atomic write,
# the state-file-out-of-the-inbox security posture, and notify.
#
# every provider with an inbox passes an explicit state_path under tmp_path -- the default
# state lives under ~/var, which a test must never touch.
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


def _provider(tmp_path, **kw):
    kw.setdefault("debounce_s", 0)
    kw.setdefault("state_path", tmp_path / "state.json")
    return FilesystemProvider(tmp_path / "inbox", **kw)


def test_read_delivers_new_sources(tmp_path):
    _drop(tmp_path / "inbox", "a.txt")
    _drop(tmp_path / "inbox", "b.txt")
    provider = _provider(tmp_path)
    assert {s.name for s in provider.read()} == {"a.txt", "b.txt"}
    # a second pass in the same process delivers nothing -- they are in flight.
    assert list(provider.read()) == []


def test_suffix_filter(tmp_path):
    _drop(tmp_path / "inbox", "a.m4a")
    _drop(tmp_path / "inbox", "note.txt")
    provider = _provider(tmp_path, suffixes={".m4a"})
    assert {s.name for s in provider.read()} == {"a.m4a"}


def test_dedup_is_recorded_on_mark_done_and_survives_restart(tmp_path):
    # deliver + mark_done, then DROP the provider (reboot) and build a fresh one over the
    # same state -> the file is NOT re-delivered.
    _drop(tmp_path / "inbox", "a.txt")
    first = _provider(tmp_path)
    [src] = list(first.read())
    first.mark_done(src)  # the bento reached a terminal state

    restarted = _provider(tmp_path)
    assert list(restarted.read()) == [], "a handled file must not be re-delivered after restart"

    # a GENUINE re-drop (mtime moves to a new, settled time) is a new fact and IS delivered.
    earlier = time.time() - 100
    os.utime(tmp_path / "inbox" / "a.txt", (earlier, earlier))
    assert {s.name for s in restarted.read()} == {"a.txt"}


def test_crash_mid_cook_redelivers_on_restart(tmp_path):
    # L1.1: read() hands out a source but the bento never reaches terminal (a crash/reboot
    # mid-cook -- the default runtime). mark_done was NOT called, so a fresh provider
    # RE-DELIVERS the source and the work completes on retry -- no silent drop.
    _drop(tmp_path / "inbox", "a.txt")
    first = _provider(tmp_path)
    [src] = list(first.read())
    # (no mark_done -- simulate the process dying before the terminal state)

    restarted = _provider(tmp_path)
    [again] = list(restarted.read())
    assert again.name == "a.txt", "a crash before terminal must re-deliver, not abandon"
    restarted.mark_done(again)  # the retry completes
    once_more = _provider(tmp_path)
    assert list(once_more.read()) == []


def test_skips_file_still_being_written(tmp_path):
    p = _drop(tmp_path / "inbox", "in-flight.txt")
    provider = _provider(tmp_path, debounce_s=30)
    assert list(provider.read()) == []  # fresh mtime -> not yet stable
    old = time.time() - 60
    os.utime(p, (old, old))
    assert {s.name for s in provider.read()} == {"in-flight.txt"}


def test_does_not_move_or_delete_the_source(tmp_path):
    p = _drop(tmp_path / "inbox", "a.txt")
    provider = _provider(tmp_path)
    list(provider.read())
    assert p.exists(), "dup-over-loss: the provider must never move or delete the source"


# --- L1.2: state file out of the inbox, hardened atomic write ----------------

def test_state_file_defaults_outside_the_inbox(tmp_path):
    # a provider with NO explicit state_path must NOT put its delivery log inside the inbox
    # (a dropper there could pre-seed it to suppress intake). The default lives under ~/var.
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    provider = FilesystemProvider(inbox, debounce_s=0)
    assert provider.state_path is not None
    assert inbox not in provider.state_path.parents
    assert "var" in provider.state_path.parts


def test_poison_state_in_inbox_does_not_suppress_intake(tmp_path):
    # an attacker drops a file named like the old in-inbox state. Because the real state is
    # elsewhere (and the dotfile is skipped by read), it does not suppress a real source.
    inbox = tmp_path / "inbox"
    _drop(inbox, ".good_citizen_delivered.json", b'{"poison": 1}')
    _drop(inbox, "real.txt")
    provider = _provider(tmp_path)
    assert {s.name for s in provider.read()} == {"real.txt"}


def test_atomic_write_leaves_no_tmp(tmp_path):
    dest = tmp_path / "out" / "result.txt"
    assert FilesystemProvider().write(str(dest), "the bytes") == str(dest)
    assert dest.read_text() == "the bytes"
    assert not list((tmp_path / "out").glob(".*tmp*"))


def test_atomic_write_replaces_in_place(tmp_path):
    dest = tmp_path / "r.txt"
    atomic_write(dest, "v1")
    atomic_write(dest, "v2")
    assert dest.read_text() == "v2"


def test_atomic_write_does_not_clobber_through_a_symlinked_dest(tmp_path):
    # a pre-planted symlink at the destination must not be written THROUGH to its target;
    # os.replace swaps the inode, so the target is untouched and the dest becomes a real file.
    target = tmp_path / "secret.txt"
    target.write_text("do not touch")
    dest = tmp_path / "manifest.json"
    dest.symlink_to(target)
    atomic_write(dest, "new content")
    assert target.read_text() == "do not touch", "must not clobber through the symlink"
    assert not dest.is_symlink()
    assert dest.read_text() == "new content"


# --- notify -------------------------------------------------------------------

def test_notify_drops_a_record(tmp_path):
    notify_dir = tmp_path / "notifications"
    provider = FilesystemProvider(notify_dir=notify_dir)
    provider.notify({"bento_id": "abc", "ok": True, "state": "DONE"})
    rec = json.loads((notify_dir / "abc.json").read_text())
    assert rec["ok"] is True and rec["state"] == "DONE"


def test_notify_without_dir_does_not_raise():
    FilesystemProvider().notify({"bento_id": "x", "ok": False, "state": "FAILED"})

# tests for good_citizen.watcher: scan_once picks up new files, honors a suffix filter,
# does not reprocess seen files, and one bad file does not abort the pass.
from good_citizen import watcher


def _drop(inbox, *names):
    inbox.mkdir(parents=True, exist_ok=True)
    for n in names:
        (inbox / n).write_bytes(b"x")


def test_scan_picks_up_new_files(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.m4a", "b.wav", "c.txt")
    handled = []
    watcher.scan_once(inbox, set(), handled.append)
    assert {p.name for p in handled} == {"a.m4a", "b.wav", "c.txt"}


def test_scan_suffix_filter(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.m4a", "note.txt")
    handled = []
    watcher.scan_once(inbox, set(), handled.append, suffixes={".m4a"})
    assert {p.name for p in handled} == {"a.m4a"}


def test_scan_does_not_reprocess_seen(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "a.m4a")
    seen = set()
    watcher.scan_once(inbox, seen, lambda p: None)
    assert watcher.scan_once(inbox, seen, lambda p: None) == []


def test_scan_one_bad_file_does_not_stop_the_rest(tmp_path):
    inbox = tmp_path / "inbox"
    _drop(inbox, "good1.m4a", "bad.m4a", "good2.m4a")
    ok = []

    def handler(p):
        if p.name == "bad.m4a":
            raise RuntimeError("boom")
        ok.append(p.name)

    handled = watcher.scan_once(inbox, set(), handler)
    assert set(ok) == {"good1.m4a", "good2.m4a"}
    assert {p.name for p in handled} == {"good1.m4a", "good2.m4a"}

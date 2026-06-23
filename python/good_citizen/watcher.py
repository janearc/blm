# good_citizen.watcher -- the generic inbox watch loop a pipeline reuses instead of
# hand-rolling one (magpie drops its own onto this at P5). scan_once is one pass and is
# testable without a running daemon; watch() is the poll loop on top of it.
#
# dup-over-loss: the watcher never moves or deletes the source. An in-memory "seen" set
# stops reprocessing within a run; a restart reprocesses whatever is still in the inbox,
# which is safe because each run is idempotent (the standalone counterpart to the bus
# redelivery the mesh uses).
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)


def scan_once(inbox, seen, handler, suffixes=None):
    # one pass: call handler(path) for each new file (optionally filtered to suffixes,
    # lowercased), recording it in `seen`. Returns the paths handled this pass. A file
    # that raises in handler is logged and skipped -- one bad file must not abort the pass.
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    handled = []
    for f in sorted(inbox.iterdir()):
        if not f.is_file() or f in seen:
            continue
        if suffixes is not None and f.suffix.lower() not in suffixes:
            continue
        seen.add(f)
        try:
            handler(f)
            handled.append(f)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the loop
            log.error("good_citizen.watcher: failed on %s: %s", f, e)
    return handled


def watch(inbox, handler, suffixes=None, interval=5.0):
    # poll the inbox forever, handling new files each pass. `seen` persists in memory
    # across passes for the life of the process.
    seen = set()
    log.info("good_citizen.watcher: watching %s", inbox)
    while True:
        scan_once(inbox, seen, handler, suffixes=suffixes)
        time.sleep(interval)

# frood.watcher -- the generic intake loop, now a thin consumer of a Provider.
#
# the watcher no longer touches the filesystem: a Provider owns intake (provider.read),
# the persistent dedup, and the partial-write guard. scan_once is one pass and is testable
# with an in-memory mock provider; watch() is the poll loop on top of it.
#
# dup-over-loss: the provider never moves or deletes the source. Dedup PERSISTS across
# restarts (the provider records what it has delivered), so a reboot -- which this laptop
# does constantly -- does not re-deliver a source or re-create its bento. A genuine re-drop
# (the operator copies the file in again, moving its mtime) is a new fact and is delivered.
import logging
import time

log = logging.getLogger(__name__)


def scan_once(provider, handler):
    # one pass: pull the newly-arrived, stable sources from the provider and hand each to
    # handler(source). Returns the sources handled this pass. A source that raises in the
    # handler is logged and skipped -- one bad source must not abort the pass.
    handled = []
    for source in provider.read():
        try:
            handler(source)
            handled.append(source)
        except Exception as e:  # noqa: BLE001 - one bad source must not stop the loop
            log.error("frood.watcher: failed on %s: %s", source.name, e)
    return handled


def watch(provider, handler, interval=5.0):
    # poll the provider forever, handling new sources each pass. Dedup is the provider's
    # job and is durable, so the loop carries no in-memory "seen" set to lose on restart.
    log.info("frood.watcher: watching via %s", type(provider).__name__)
    while True:
        scan_once(provider, handler)
        time.sleep(interval)

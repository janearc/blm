# frood.provider -- the one I/O seam every pipeline routes through.
#
# ALL inbox intake (read), output emission (write), and result notification (notify) go
# through a Provider, so swapping the filesystem for S3 / Google Drive / rsync / a tunnel
# collector is a CONFIG change, not a code change. Only FilesystemProvider exists today --
# this lands the SEAM, not the other backends. The interface is designed against two
# near-term uses so it is the right shape: (a) a phone-visible synced folder, and (b) a
# record-on-the-spot URL over a tunnel that appends to a collector. Both are a provider
# swap, not a rewrite.
#
# laptop-resilience is a correctness requirement here: the box sleeps and reboots
# constantly. Delivery is recorded only AFTER a bento reaches a terminal state, so a crash
# mid-cook RE-DELIVERS on restart rather than abandoning the work -- at-least-once, which
# upholds dup-over-loss and never-silent. dup-over-loss also holds at intake: the provider
# never moves or deletes the source, and a genuine re-drop (the file changes) is a new fact.

import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    # one item of intake. `id` is the STABLE dedup key; `name` is the display/filename;
    # `location` is where the consumer reads or copies the bytes from. the provider never
    # moves or deletes the underlying source.
    id: str
    name: str
    location: str


@runtime_checkable
class Provider(Protocol):
    # the I/O contract. read() yields newly-arrived, stable, not-yet-delivered sources WITHOUT
    # recording them as done. mark_done() records a source as delivered, durably, once its
    # bento has reached a terminal state -- so a crash before terminal re-delivers. write()
    # emits an artifact/record atomically. notify() announces a terminal result.
    def read(self) -> Iterable[Source]: ...
    def mark_done(self, source: Source) -> None: ...
    def write(self, location: str, data) -> str: ...
    def notify(self, record: dict) -> None: ...


def atomic_write(location, data) -> str:
    # write via an UNPREDICTABLE temp file (tempfile.mkstemp, O_CREAT|O_EXCL, mode 0600) in
    # the destination directory, then os.replace onto the target. mkstemp's exclusive,
    # random name means an attacker cannot pre-plant a symlink at a predictable tmp path to
    # be followed (the old `.{name}.{pid}.tmp` could be), and os.replace swaps the inode
    # rather than writing THROUGH a symlinked destination. a reader never sees a half-write.
    path = Path(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode() if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        # never leave a tmp behind on a failed write.
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return str(path)


class FilesystemProvider:
    # the only provider today. read() watches an inbox dir; write() lands files on the local
    # fs atomically; notify() drops a JSON record into a notifications dir a phone-synced
    # folder (or another watcher) can see, and always logs the announcement.
    #
    # persistent dedup: a source is recorded delivered (keyed on path+size+mtime) only when
    # mark_done() is called -- after its bento reaches a terminal state. An in-memory
    # in-flight set stops the same process from handing a source out twice while it cooks; a
    # RESTART starts with an empty in-flight set, so anything that was mid-cook at the crash
    # is re-delivered (at-least-once). The delivery log lives OUTSIDE the inbox (default
    # under ~/var/frood) so a dropper cannot pre-seed it to suppress intake.

    def __init__(
        self,
        inbox=None,
        *,
        suffixes=None,
        notify_dir=None,
        state_path=None,
        debounce_s=2.0,
    ):
        self.inbox = Path(inbox) if inbox is not None else None
        self.suffixes = {s.lower() for s in suffixes} if suffixes else None
        self.notify_dir = Path(notify_dir) if notify_dir is not None else None
        self.debounce_s = debounce_s
        self.state_path = self._resolve_state_path(state_path)
        self._delivered = self._load_state()
        self._inflight: set[str] = set()

    def _resolve_state_path(self, state_path):
        # the delivery log MUST NOT live inside the inbox -- the inbox is the scary-world
        # drop surface (a synced folder, a tunnel collector), and a dropper that could
        # pre-seed the state there would silently suppress intake (or poison json.loads). A
        # caller SHOULD pass an explicit state_path under its own ~/var/<service>; absent
        # that, default under ~/var/frood, keyed by the inbox path.
        if state_path is not None:
            return Path(state_path)
        if self.inbox is None:
            return None
        digest = hashlib.sha256(str(self.inbox.resolve()).encode()).hexdigest()[:16]
        return Path.home() / "var" / "frood" / f"delivered-{digest}.json"

    # --- read: intake; dedup is recorded on mark_done, not here ----------------
    def read(self) -> Iterable[Source]:
        # yield new, stable sources that are neither already delivered (durable) nor already
        # in flight in THIS process. A file still being written (mtime within the debounce)
        # is skipped and picked up on a later pass. recording delivery is mark_done()'s job,
        # after the bento goes terminal -- so a crash mid-cook re-delivers on restart.
        if self.inbox is None:
            return []
        self.inbox.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(self.inbox.iterdir()):
            if not p.is_file() or p.name.startswith("."):
                continue  # skip hidden bookkeeping (and never the state file -- it's elsewhere)
            if self.suffixes is not None and p.suffix.lower() not in self.suffixes:
                continue
            try:
                key = self._key(p)
            except FileNotFoundError:
                continue  # vanished mid-scan
            if key in self._delivered or key in self._inflight:
                continue
            if not self._is_stable(p):
                continue  # still being written -- a later pass will catch it once quiet
            self._inflight.add(key)
            out.append(Source(id=key, name=p.name, location=str(p)))
        return out

    def mark_done(self, source: Source) -> None:
        # record a source as delivered, DURABLY, now that its bento has reached a terminal
        # state. only after this will a restart decline to re-deliver it.
        self._delivered[source.id] = time.time()
        self._save_state()
        self._inflight.discard(source.id)

    def _key(self, p: Path) -> str:
        # the dedup key: path + size + mtime. a genuine re-drop changes size or mtime, so it
        # is a new key (delivered again); an identical file after a restart is the same fact.
        st = p.stat()
        return f"{p}:{st.st_size}:{int(st.st_mtime)}"

    def _is_stable(self, p: Path) -> bool:
        # the partial-write guard: a file is stable once its mtime has been quiet for
        # debounce_s. an in-flight scp / iOS drop keeps bumping mtime, so it is held until
        # the writer stops. debounce_s=0 treats everything as stable (tests, trusted drops).
        try:
            return (time.time() - p.stat().st_mtime) >= self.debounce_s
        except FileNotFoundError:
            return False

    def _load_state(self) -> dict:
        if self.state_path is not None and self.state_path.is_file():
            try:
                return json.loads(self.state_path.read_text())
            except Exception as e:  # noqa: BLE001 - a corrupt state file must not wedge intake
                log.warning(
                    "frood.provider: unreadable delivery state %s (%s); starting empty",
                    self.state_path, e,
                )
        return {}

    def _save_state(self) -> None:
        if self.state_path is not None:
            atomic_write(self.state_path, json.dumps(self._delivered))

    # --- write: atomic output emission ----------------------------------------
    def write(self, location: str, data) -> str:
        # land `data` at `location` on the fs, atomically. returns the location.
        return atomic_write(location, data)

    # --- notify: announce a terminal result -----------------------------------
    def notify(self, record: dict) -> None:
        # announce a terminal result: always log it, and -- when a notify_dir is set -- drop
        # an atomic JSON record a phone-synced folder or another watcher can see. a non-fs
        # provider (S3/collector/tunnel) POSTs instead; the caller does not change.
        ident = record.get("bento_id") or record.get("id") or str(time.time())
        log.info("frood.provider: notify %s ok=%s state=%s",
                 ident, record.get("ok"), record.get("state"))
        if self.notify_dir is not None:
            atomic_write(self.notify_dir / f"{ident}.json", json.dumps(record, indent=2))

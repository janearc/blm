# good_citizen.provider -- the one I/O seam every pipeline routes through.
#
# ALL inbox intake (read), output emission (write), and result notification (notify) go
# through a Provider, so swapping the filesystem for S3 / Google Drive / rsync / git / a
# tarball / a tunnel collector is a CONFIG change, not a code change. Only FilesystemProvider
# exists today -- this lands the SEAM, not the other backends. The interface is designed
# against two near-term uses so it is the right shape: (a) a phone-visible synced folder
# (read = the synced dir, notify = a record the phone sees), and (b) a record-on-the-spot
# URL over a tunnel that appends to a collector (read = the collector's new items, notify =
# a POST back). Both are a provider swap, not a rewrite.
#
# laptop-resilience is a correctness requirement here: the box sleeps and reboots
# constantly, so dedup MUST persist across restarts -- a restart must not re-deliver a
# source or re-create its bento. dup-over-loss still holds: the provider never moves or
# deletes the operator's source, and a genuine re-drop (the file changes) is a new fact.

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    # one item of intake. `id` is the STABLE persistent-dedup key (so a restart does not
    # re-deliver); `name` is the display/filename; `location` is where the consumer reads
    # or copies the bytes from. the provider never moves or deletes the underlying source.
    id: str
    name: str
    location: str


@runtime_checkable
class Provider(Protocol):
    # the I/O contract. read() yields newly-arrived, stable, not-yet-delivered sources and
    # records the delivery durably. write() emits an artifact/record to a destination
    # atomically. notify() announces a terminal result so a consumer/operator sees it.
    def read(self) -> Iterable[Source]: ...
    def write(self, location: str, data) -> str: ...
    def notify(self, record: dict) -> None: ...


def atomic_write(location, data) -> str:
    # write via a sibling tmp + os.replace, so a reader (a poll, another instance, a synced
    # client) never sees a half-written file. the tmp shares the destination directory so
    # the replace is atomic (same filesystem). accepts str or bytes.
    path = Path(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode() if isinstance(data, str) else data
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(payload)
        os.replace(tmp, path)
    finally:
        # never leave a .tmp behind on a failed write (a half-write must not litter the sink).
        if tmp.exists():
            tmp.unlink()
    return str(path)


class FilesystemProvider:
    # the only provider today. read() watches an inbox dir; write() lands files on the local
    # fs atomically; notify() drops a JSON record into a notifications dir a phone-synced
    # folder (or another watcher) can see, and always logs the announcement.
    #
    # persistent dedup: delivered sources are recorded to a state file (keyed on
    # path+size+mtime), atomically, so a RESTART does not re-deliver. a genuine re-drop --
    # the operator copies the file in again, which moves its mtime -- is a NEW key and is
    # delivered. the source itself is never moved or deleted (dup-over-loss).

    def __init__(
        self,
        inbox=None,
        *,
        suffixes=None,
        notify_dir=None,
        state_path=None,
        debounce_s=2.0,
    ):
        # inbox/suffixes drive read(); notify_dir is where notify() drops records; state_path
        # is the persistent delivery log (defaults under the inbox, hidden). debounce_s is the
        # partial-write guard: a file whose mtime is younger than this is "still being
        # written" and is held until it goes quiet. set debounce_s=0 to deliver immediately.
        self.inbox = Path(inbox) if inbox is not None else None
        self.suffixes = {s.lower() for s in suffixes} if suffixes else None
        self.notify_dir = Path(notify_dir) if notify_dir is not None else None
        self.debounce_s = debounce_s
        if state_path is not None:
            self.state_path = Path(state_path)
        elif self.inbox is not None:
            self.state_path = self.inbox / ".good_citizen_delivered.json"
        else:
            self.state_path = None
        self._delivered = self._load_state()

    # --- read: intake with persistent dedup + a partial-write guard -----------
    def read(self) -> Iterable[Source]:
        # yield new, stable, not-yet-delivered sources, recording each delivery durably so a
        # restart will not re-deliver it. a file still being written (mtime within the
        # debounce) is skipped and picked up on a later pass. a write-only provider (no
        # inbox) yields nothing.
        if self.inbox is None:
            return []
        self.inbox.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(self.inbox.iterdir()):
            if not p.is_file() or p.name.startswith("."):
                continue  # skip the state file and other hidden bookkeeping
            if self.suffixes is not None and p.suffix.lower() not in self.suffixes:
                continue
            try:
                key = self._key(p)
            except FileNotFoundError:
                continue  # vanished mid-scan
            if key in self._delivered:
                continue
            if not self._is_stable(p):
                continue  # still being written -- a later pass will catch it once quiet
            self._delivered[key] = time.time()
            self._save_state()
            out.append(Source(id=key, name=p.name, location=str(p)))
        return out

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
                    "good_citizen.provider: unreadable delivery state %s (%s); starting empty",
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
        log.info("good_citizen.provider: notify %s ok=%s state=%s",
                 ident, record.get("ok"), record.get("state"))
        if self.notify_dir is not None:
            atomic_write(self.notify_dir / f"{ident}.json", json.dumps(record, indent=2))

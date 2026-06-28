# Providers: the I/O seam

A pipeline does three kinds of I/O: it takes work in, it emits results out, and it announces
that a result is ready. In blm all three go through one seam — a **Provider** — so *where*
the work comes from and *where* the results go is configuration, not code.

    read    intake          -> new units of work
    write   output          -> an artifact / record landed at a destination
    notify  notification    -> "a result is ready"

`good_citizen.provider` defines the contract and ships one implementation,
`FilesystemProvider`. The watcher is a thin consumer of `read`; the birb scaffold routes
every write through `write` and announces every terminal through `notify`.

## The contract

```python
class Provider(Protocol):
    def read(self) -> Iterable[Source]: ...   # new, stable, not-yet-delivered units
    def write(self, location: str, data) -> str: ...   # land it atomically; return where
    def notify(self, record: dict) -> None: ...        # announce a terminal result
```

A `Source` is one unit of intake: a stable `id` (the dedup key), a `name`, and a `location`
the consumer reads from.

## What `FilesystemProvider` guarantees

- **Atomic, symlink-safe writes.** `write` lands data via an *unpredictable* temp file
  (`tempfile.mkstemp`, exclusive, mode 0600) + `os.replace`, so a reader never sees a
  half-written file, and an attacker cannot pre-plant a symlink at a predictable temp path to
  be followed (and `os.replace` swaps the inode rather than writing *through* a symlinked
  destination).
- **At-least-once dedup, recorded on terminal.** A source is recorded delivered (keyed on
  path+size+mtime) only **after its bento reaches a terminal state** — not at intake. The
  default environment is a laptop that sleeps and reboots constantly; recording on terminal
  means a crash *mid-cook* re-delivers the source on restart (the work completes on retry)
  rather than marking it done and abandoning it. A source already carried to a terminal state
  is not re-delivered. An in-memory in-flight set stops the same process from handing a source
  out twice while it cooks.
- **The delivery log lives outside the inbox.** It defaults under `~/var` (a service SHOULD
  pass its own path under `~/var/<service>`), never inside the drop directory — the inbox is
  the scary-world surface, and a dropper there must not be able to pre-seed the state to
  suppress intake.
- **Duplicates over loss.** The provider never moves or deletes the source. A genuine
  re-drop — the operator copies the file in again, which moves its mtime — is a new unit and
  is delivered again.
- **A partial-write guard.** A source whose mtime is still fresh (an in-flight scp, an iOS
  drop) is held until it goes quiet, so the consumer never picks up a file mid-write.

## Why a seam, not just a folder

The seam is shaped against two near-term uses, so swapping the backend is a config change,
not a rewrite:

- a **phone-visible synced folder** — `read` watches the synced directory; `notify` drops a
  record the phone sees;
- a **record-on-the-spot URL over a tunnel** that appends to a collector — `read` yields the
  collector's new items; `notify` POSTs back.

## Other backends: marked, not built

Only `FilesystemProvider` exists today. S3, Google Drive, rsync, git, a tarball, and a tunnel
collector are **marked destinations**, not implementations — each is a future `Provider`, and
adopting one is a configuration choice at the daemon, not a change to a watcher, a handler, or
a birb. The artifact/source *paths* a non-filesystem provider hands back (an object key, a
URL) are the next layer to generalize; the intake and notification halves are swappable today.

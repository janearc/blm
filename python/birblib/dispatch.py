# birblib.dispatch -- the one gated-dispatcher backend seam.
#
# the research birbs grew three drifted idioms for "pick a backend": a registry+Protocol
# whose available() had already skewed to a bare bool (grackle), a single swappable
# function (lloyd), and an ad-hoc gated dispatcher that recorded WHY it chose what it
# chose (turtledove). the third is the best, and this is it, generalized: one Backend
# protocol and one dispatch() that probes in order, runs the first usable backend, falls
# through on a RUNTIME failure to the next, and NEVER fabricates a result. it returns the
# full decision tree as `detail` -- which were probed, what each reported, which ran --
# so a manifest can answer "what did the work, and why this and not that".

from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    # a backend names itself, reports whether it can run (with a REASON, not a bare bool --
    # the reason is what makes the decision tree legible), and runs. run()'s signature is
    # the birb's to define; dispatch() forwards whatever args it is given.
    name: str

    def available(self) -> tuple[bool, str]:
        # (ok, reason). "ollama up; mistral pulled" / "apple-fm-sdk not installed".
        ...

    def run(self, *args, **kwargs):
        ...


class NoBackendAvailable(RuntimeError):  # noqa: N818 - reads as a condition, like ModelUnavailable
    # no backend in the set was usable. carries the decision tree as .detail so a caller
    # that degrades (raw beats nothing) can still record WHY every backend was passed over.
    def __init__(self, detail: dict) -> None:
        # name what was probed and why each was passed over; "<none probed>" when the
        # backend set was empty (the concatenation is always truthy, so the fallback has to
        # wrap the join, not the whole string).
        tried = detail.get("tried", {})
        probed = ", ".join(f"{name} ({why})" for name, why in tried.items()) or "<none probed>"
        super().__init__("no backend available: " + probed)
        self.detail = detail


def _order(backends, prefer):
    # the probe order: a preferred backend (by name) first, then the declared order, with
    # duplicates removed. an unknown prefer name is ignored (it simply never matches).
    if not prefer:
        return list(backends)
    by_name = {b.name: b for b in backends}
    if prefer not in by_name:
        return list(backends)
    return [by_name[prefer]] + [b for b in backends if b.name != prefer]


def dispatch(backends, *args, prefer=None, **kwargs):
    # probe `backends` in order (prefer first), run the first one that reports available,
    # and return (output, detail). a backend that is available but RAISES at run time is
    # recorded and skipped -- a runtime failure must never fake a result, it falls through
    # to the next. if none is usable, raise NoBackendAvailable(detail) -- the caller
    # decides whether that degrades (keep the input) or fails the bento. `detail` is the
    # decision tree: {"backend": <ran>, "tried": {name: reason, ...}}.
    tried: dict[str, str] = {}
    for backend in _order(backends, prefer):
        ok, why = backend.available()
        tried[backend.name] = why
        if not ok:
            continue
        try:
            output = backend.run(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - available but failed: record it and fall through
            tried[backend.name] = f"available but failed: {e}"
            continue
        return output, {"backend": backend.name, "tried": tried}
    raise NoBackendAvailable({"backend": None, "tried": tried})

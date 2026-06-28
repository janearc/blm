# Bento states: the lifecycle and its obligations

This is the normative companion to [pipelines.md](pipelines.md). It states, per state, what
a handler MUST and MAY do. The key words MUST, MUST NOT, SHOULD, and MAY are used as in
RFC 2119.

A bento moves through one small machine:

    NOTICED -> COOK -> DONE
                   \-> PARTIAL -> DONE
                   \-> FAILED

The machine emits and consumes events; it does not reason about the world. **The bus is the
loop:** one handler advances a bento one step per consumed event, then returns. A process MAY
die between steps; another instance resumes from the bus. Every step therefore MUST be
idempotent — re-handling the same event MUST NOT duplicate a side effect.

## The active states

### `NOTICED` — a bento has appeared; pre-flight has not run
The `on_noticed` handler MUST establish the bento's workspace and verify its inputs before
any processing. It:
- MUST be idempotent (a redelivered `NOTICED` re-runs pre-flight without harm).
- MUST NOT move or delete the operator's source input (**duplicates over loss**); it copies
  the source into the bento and repoints the banchan at the copy.
- MUST persist the bento's resolved request so a replay can reconstruct intent.
- MUST transition to `FAILED` if a required input is absent or unreadable.
- Returns `COOK` when the bento is ready to process.

### `COOK` — a handler is processing the bento
The `on_cook` handler does the work. The stages it runs inside `COOK` (transcribe, render,
clean, …) are the handler's own business and MUST NOT appear on the wire as states.
- It MUST produce exactly one of three outcomes: a clean result (`DONE`), a degraded but
  usable result (`PARTIAL`), or a failure (`FAILED`).
- A step that **cannot** degrade (the irreducible work) MUST raise on error; the harness
  takes that to `FAILED`.
- A run that completes with **no artifact** (the input was rejected or the result was empty)
  MUST be a visible non-success — `FAILED` with the reason recorded — never a silent `DONE`.
  (`SPOILED` is the reserved home for "rejected"; until it is wired, `FAILED` carries it.)
- It MUST write the manifest and notify before the bento comes to rest (see *Never-silent*).

### `PARTIAL` — best-effort: worked, owned, not finished
Reserved for substrate-owned **convergence**, which is undefined today. The `on_partial`
handler is the convergence seam.
- The default `on_partial` MUST accept the degraded artifact and return `DONE` (a usable
  result beats nothing), recording the degrade in the manifest's `detail`.
- A handler MAY override `on_partial` to loop toward convergence once that policy is defined.
- A bento MUST NOT come to rest in `PARTIAL`; it resolves to `DONE` (or, by an override, back
  to `COOK`).

### `DONE` — processed; output written. Terminal.
`on_done` is terminal. The outputs and the manifest were written before the transition, so
`on_done` MUST NOT do further work. It returns the halt signal.

### `FAILED` — could not proceed, or processing errored. Terminal.
`on_failed` is terminal. The manifest (carrying the reason in `detail.error`) was written at
the point of failure, so `on_failed` MUST NOT do further work. It returns the halt signal.

## Reserved states
`CHEW`, `DIGEST`, and `SPOILED` are declared to hold the namespace. A handler MUST NOT emit a
reserved state — the harness rejects an undeclared transition. `SPOILED` is the intended home
for a rejected/unusable input; until its behavior is defined and wired, a zero-artifact run
terminates `FAILED`.

## Never-silent (the cross-cutting obligation)
No code path may bring a bento to a terminal state without BOTH:
1. a **manifest written at the sink** a consumer expects (carrying `ok` = `state == DONE`,
   the terminal `state`, and the reason), AND
2. a **notification** that the result is ready.

This holds on `DONE`, on `FAILED`, and on a zero-artifact reject alike. A terminal bento with
no manifest, or no notification, is a defect.

## The success signal
`ok` is the single success signal, and `ok == (state == DONE)`. A degrade that was accepted is
`DONE`/`ok` with the degrade recorded in `detail`; a rejected or errored run is `FAILED`/not
`ok` with the reason in `detail`. There is no `ok` `DONE` without an artifact.

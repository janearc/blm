# Contributing to blm

## Version discipline (the 0.4.x convergence line)

blm is converging toward a stable freeze. During convergence:

- **Version numbers are finite — do not burn one per fix.** The `0.4.x` line is the
  convergence line. Batch related work; prefer a force-push over minting a new patch number.
  A version bump marks a deliberate, named step, not every diff.
- **Force-pushing `main` is acceptable during convergence.** Getting it *stable* outranks
  preserving a tidy linear history. This is a property of the convergence phase and ends at
  the freeze.
- **`0.5` is the freeze.** At `0.5` everything is tagged together — the contracts,
  `good_citizen`, `birblib`, and the birbs — as one coherent cut, and we ship a "here's blm"
  write-up against that tag. `0.5` is not a feature target reached by accumulating minor
  bumps; it is the moment we decide the core is done and stop moving it.

A practical consequence: a stacked review (e.g. a `good_citizen` change and the `birblib`
change that consumes it) lands as a tight set of PRs, not a version bump each.

## The stability / seam boundary

Convergence freezes the **batch core** and leaves the **streaming-and-beyond seams**
explicitly open. Knowing which side of the line a thing is on tells you whether changing it is
a convergence concern (careful, contract-grade) or an open question (expected to move).

**Freezing at `0.5` — change these carefully, they are becoming contract:**

- the data model: `bento` and `banchan` (`bento.proto`);
- the lifecycle walk: `NOTICED → COOK → (DONE | PARTIAL → DONE | FAILED)` and its
  never-silent obligation (a terminal bento always has a manifest at the sink + a notify);
- the manifest envelope (`ok`/`state`/`artifact`/`params`/`stats`/`detail`) and its
  marked promotion target, the additive `BentoManifest` message;
- the gated backend selection (`birblib.dispatch`): probe in order, never fabricate, record
  the decision tree;
- the I/O seam shape (`Provider`: `read`/`write`/`notify`) and the filesystem implementation.

**Explicitly open — expected to move, not frozen at `0.5`:**

- the streaming / near-real-time / callback processing mode (the batch guarantees inverted);
- the convergence policy (the `PARTIAL` loop is a documented stopgap; the real policy is
  undefined — see [pipelines.md](docs/pipelines.md#convergence));
- composition and destinations (how a bento describes what it wants to become);
- the non-filesystem providers (S3 / Drive / rsync / tunnel collector) — the seam is frozen,
  the other backends are not built;
- reserved states (`CHEW`, `DIGEST`, `SPOILED`) — declared, not wired.

If you are changing something on the frozen side, treat it as a contract change: it gets the
careful review and the gen-drift/CI gates. If it is on the open side, say so in the PR — it is
allowed to be provisional.

## Quality gates

Every change runs the same gates locally and in CI: `ruff` (E,F,B,N,T201 @ 100), the
docstring ban (intent in `#` comments, never docstrings), `pytest`, and — for any proto
change — `buf generate` with the committed gen in sync (the gen-drift gate). Lint and tests
pass before a push.

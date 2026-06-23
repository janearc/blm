# Pipelines: bento, banchan, and the pipeline-pipeline

blm describes how pipelines are built. It is a library and a set of protobuf
contracts, not a daemon -- there is no `blmd`. A pipeline built on blm is a project
that the orchestrator (delightd) registers and that the mesh composes.

## The data model

Work moves through the mesh in **bentos**. A bento is a batch -- the unit of work
that flows through a pipeline. A bento is made of **banchans**: irreducible elements
of the batch (raw logs, a prompt, an audio file, a produced transcript). A banchan is
a member, not a step. It carries a guid, a location, and *assets* -- checks such as a
pre-flight, an acceptance test, or a compatibility test. A bento is complete when its
declared banchans are present and their assets pass.

The naming is deliberate: a bento is a box, and banchans are the things that fit in
it. The words are meant to be obvious.

## The lifecycle

A bento flows through a small state machine:

    NOTICED -> COOK -> DONE
                   \-> PARTIAL
                   \-> FAILED

`NOTICED` means a bento has appeared. `COOK` is the processing -- the work a handler
does to transform a bento's banchans. `DONE` means the output is written. `PARTIAL`
means best-effort: worked, owned, not finished. `FAILED` means it could not proceed.

The state machine is deliberately dumb. It emits events and consumes events; it does
not reason about the world. A handler reacts to the state for the bento guids it owns,
does its work, and emits the next state. No event, no handler call. A few states are
reserved for later use and are not wired until they have defined behavior.

The stages inside `COOK` (for a transcription pipeline: transcribe, then clean) are
the handler's own business, not the contract's. The contract carries the data and the
lifecycle; the behavior lives in the handler.

## Convergence

Some pipelines are recursive: they process a bento, check whether the result is
acceptable, and process it again until it converges -- training loops, character
development. A pipeline declares itself converging; the machine does not care, it only
allows the loop. Convergence is internal to a bento, declaratively described (intent,
not a shell script), and separately bounded. Its specification is not yet defined. It
is distinct from routing: a convergence pass is not a routing hop.

## Routing and composition

This is a pipeline-of-pipelines. The output of one pipeline can feed another:
transcribe an audio note and then generate a video from it; turn a document into a
podcast. A bento carries a **route** -- where its output should go when it completes.

The route is data. It never changes how a bento is processed; the machine reads it at
exactly one moment, the `DONE` transition, and emits a hand-off to the target. The
target consumes the hand-off and spawns a new bento from the outputs. The pipelines
never know about each other -- they only know the bus.

Each bento carries an **itinerary**: the ordered list of pipeline guids it has passed
through. This is its provenance and its cycle guard -- a pipeline guid already in the
itinerary means a loop. The itinerary is bounded; a pipeline that tries to stamp past
the bound fails the bento and drops it rather than spiralling. Cross-pipeline routing
stays acyclic; a pipeline's own convergence loop is the only sanctioned cycle.

## The registry is delightd

A pipeline is a kind of project, and the orchestrator (delightd) is the registry. On
wake, a pipeline registers with delightd and then stays quiet until the bus gives it
work.

The registry is deliberately thin:

- It does **not** hold the bento shapes a pipeline accepts. A pipeline knows its own
  acceptable bentos; it looks at what arrives and decides. Avoiding a route-time shape
  check is a choice -- the alternative is a heavyweight registry we do not want.
- Pipelines do **not** query one another for liveness. A pipeline has no concept that
  other pipelines exist. It emits to the bus, and the target consumes when it is up;
  the bus's durability is the self-healing. Heartbeat, health, and stats exist for
  observability to watch, not for pipelines to interrogate each other. The orchestrator
  holds the global view; the pipelines do not.

## Running without the orchestrator

A pipeline's core work runs standalone, without delightd. A transcription pipeline
transcribes a file from its command line with no mesh at all. Mesh participation --
registration, routing, composition, discovery -- is what depends on delightd.

"Runs locally without delightd" is an invariant: the core never depends on the
orchestrator; only the mesh features do. Where a mesh dependency is absent, a pipeline
degrades rather than failing -- it does the part it can and keeps the raw result (the
`PARTIAL` state). The price of admission to the *mesh* -- composition, routing, the
registry -- is infrastructure; the price of running a single pipeline is not.

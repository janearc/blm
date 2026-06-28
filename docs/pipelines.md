# Pipelines: bento, banchan, and the pipeline-pipeline

blm describes how pipelines are built. It is a library and a set of protobuf
contracts, not a daemon -- there is no `blmd`. A pipeline built on blm is a project
that the orchestrator, [delightd](https://github.com/janearc/delightd), registers and
that the mesh composes.

## The data model

Work moves through the mesh in **bentos**. A bento is a batch -- the unit of work
that flows through a pipeline. A bento is made of **banchans**: irreducible elements
of the batch (raw logs, a prompt, an audio file, a produced transcript). A banchan is
a member, not a step. It carries a guid, a location, and *assets* -- checks such as a
pre-flight, an acceptance test, or a compatibility test. A bento is complete when its
declared banchans are present and their assets pass.

The naming is deliberate, and so is the relationship: banchans **snap into** a bento
the way blocks snap together. They are not independent things that happen to sit near
each other -- they *belong* to the bento, and the bento is the set of them. A bento is
a box; banchans are the things that fit it. The words are meant to be obvious on
sight.

## The lifecycle

A bento flows through a small state machine:

    NOTICED -> COOK -> DONE
                   \-> PARTIAL
                   \-> FAILED

`NOTICED` means a bento has appeared. `COOK` is the processing -- the work a handler
does to transform a bento's banchans. `DONE` means the output is written. `PARTIAL`
means best-effort: worked, owned, not finished. `FAILED` means it could not proceed.

The state machine is deliberately **simple**. It emits events and consumes events; it
does not reason about the world. A handler reacts to the state for the bento guids it
owns, does its work, and emits the next state. No event, no handler call. A few states
are reserved for later use and are not wired until they have defined behavior.

The stages a handler runs inside `COOK` are its own business, not the contract's, and
they **stay inside the handler** -- they are not states on the wire. The contract
carries a few shared states, not one per stage, and it forbids emitting an internal
step to the mesh. If a handler tries to put an internal `COOK` step onto the bus for
other pipelines to see, it fails -- either the message will not marshal, or it lands on
the bus with no home and is silently dropped, and that failure can be hard to trace.
This is central to how blm works as a mesh: the shared vocabulary is small on purpose.

A worked example -- magpie ingesting audio:

    audio file appears
      -> transcribe to text
      -> clean the text
      -> a model reformats the text to make sense of the input prompt
      -> a final pass renders it to HTML and PDF

Every arrow there is a stage *inside* `COOK`. None of them is a state. The pipeline
runs them, checks the result, and runs again until it is satisfied -- or stops because
it cannot make progress (`PARTIAL`), or gives up (`FAILED`; this happens with audio,
and that is fine). What it does **not** do is mint a `TO_PRETTY_HTML` state and a
`TO_MODEL_FOR_CLEANING` state and a hundred more. Nobody can hold a state machine with
nine hundred vanity events in their head, so we do not build one.

## Convergence

Some pipelines are recursive: they process a bento, check whether the result is
acceptable, and process it again until it converges -- training loops, character
development. A pipeline declares itself converging; the machine does not care, it only
allows the loop. Convergence is internal to a bento, declaratively described (intent,
not a shell script), and separately bounded. Its specification is not yet defined.

## Composition and destinations

blm is a pipeline-of-pipelines. The output of one pipeline can become the input of
another: an audio note transcribed and then turned into a video; a document turned
into a podcast.

We do **not** do this by handing a bento a prescribed route of hops. A bento instead
*describes what it wants to become*, in its assets -- "I am an audio file that wants to
be a podcast." It is dropped into a pipeline's inbox; the pipeline does its work; and
when it finishes, the pipeline works out the **next destination** from the bento's own
description and type. No pipeline is told a multi-step path, and no bento is dragged
along a wire of fixed stops.

(The terminology wants care -- "destination," not "route," precisely because "route"
implies prescribed hops, which we are not allowing. Exactly how a bento carries this
and how a pipeline reads it has open questions still to settle.)

A bento also carries an **itinerary**: the ordered list of the pipelines that have
already handled it. Each entry is a **stamp** -- and "stamp" is the word we use on
purpose for an itinerary element: a single pipeline's guid, recorded as the bento
passes through. The itinerary is history, not a plan -- the bento's provenance and its
cycle guard. A pipeline guid already stamped means a loop; the itinerary is bounded,
and a pipeline that would stamp past the bound fails the bento and drops it rather than
let it spiral. A pipeline's own convergence loop is the one sanctioned cycle;
cross-pipeline travel does not circle back.

## Taxonomy: project ⊇ pipeline ⊇ birb

Three nested terms, widest first:

- A **project** is the canonical unit the orchestrator manages — anything with a name and a
  git/deploy identity. Every service in the roster is a project.
- A **pipeline** is a project that does work on bentos: it has an inbox, walks bentos through
  the lifecycle, and participates in the mesh. Every pipeline is a project; not every project
  is a pipeline (a dashboard, a transfer tool, the orchestrator itself are projects, not
  pipelines).
- A **birb** is a pipeline built on the shared archetype layer, `birblib` — a thin subclass
  that declares its kind, banchans, and recipe and implements one method, `cook()`. Every
  birb is a pipeline; not every pipeline is a birb.

The last distinction matters because it is easy to assume "pipeline" and "birb" are synonyms.
They are not. **paling — the voice fine-tuner — is a pipeline but not a birb.** It predates the
archetype, carries its own bento notion, and is a different animal: an eel, not a bird. It is a
first-class citizen of the mesh (it speaks the bus, it has bentos) without subclassing
`birblib`. `birblib` is one *way* to build a pipeline, not the definition of one; `good_citizen`
— the bus/mesh citizen layer — is what every pipeline shares, birb or eel.

## Registration

A pipeline is a kind of project, and the registry is the orchestrator,
[delightd](https://github.com/janearc/delightd). On wake a pipeline registers with it,
then stays quiet until the bus gives it work. How delightd records a pipeline,
discovers it, and reports its health is delightd's to document --
see [delightd's architecture](https://github.com/janearc/delightd/blob/main/docs/architecture.md)
-- and it is deliberately *not* repeated here, because documenting one package's
internals inside another is how docs decouple, drift, and start to lie.

What belongs here is the pipeline's side:

- A pipeline knows its own acceptable bentos and decides for itself what it can handle.
  The registry does not hold that, and there is no route-time shape check -- the
  receiver looks at what arrives and accepts or declines.
- Bento definitions are intended to live in blm (a `bento-definitions` area) so that a
  pipeline vendors a shared definition rather than re-declaring it -- though a pipeline
  that wants to declare its own is free to. (Not built yet.)

## The guiding principle: a pipeline cannot reach into another

This is the rule the whole design rests on, so it is stated plainly: **a pipeline has
no concept that any other pipeline exists, and it cannot reach into one.** It does not
ask another pipeline whether it is awake. It does not read another's state. It emits to
the bus and does its job; if a destination is not up, the message waits on the bus
until it is. Heartbeat, health, and stats exist for observability to watch -- never for
pipelines to interrogate one another. The orchestrator may hold a global view; a
pipeline may not.

This is not new or clever. It is encapsulation, and the discipline of not coveting your
neighbor's internals is decades old -- Ovid's
["thou shalt not covet thy neighbor's object internals"](https://github.com/janearc/misc/blob/master/thou-shalt-not-covet/perlmonks-75578-covet-object-internals.md)
said it on PerlMonks long ago. People bristle at the constraint; it is nonetheless just
how grown-ups write code, and this mesh only models a pattern that has been understood
for a very long time.

## Running without the orchestrator

A pipeline's core work runs standalone, without delightd. A transcription pipeline
transcribes a file from its command line with no mesh at all. Mesh participation --
registration, composition, being discovered -- is what depends on delightd.

"Runs locally without delightd" is an invariant: the core **cannot** depend on the
orchestrator; only the mesh features may. Where a mesh dependency is absent a pipeline
degrades rather than fails -- it does the part it can and keeps the raw result (the
`PARTIAL` state). The price of admission to the *mesh* -- composition, the registry --
is infrastructure; the price of running a single pipeline is not.

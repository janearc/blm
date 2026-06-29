# Services: the listener archetype (resident, queried, stateful)

Big Little Mesh has had one frood archetype: the pipeline -- the **watcher**. Work is pushed
into it, it watches its inbox for churn, walks each bento through a state machine, and
when the work is done it is done. It owns no durable store; it is, in the way that
matters, ephemeral. That archetype is described in [pipelines.md](pipelines.md).

This document describes the second archetype: the resident service -- the **listener**.
A listener is not fed; it is *queried*. It parks on a socket, answers requests, and owns
durable state. Both are first-class froods of the same mesh, built on the same shared
layer; they differ in how they wake, what they keep, and how long they live.

## Two archetypes

| | WATCHER (pipeline) | LISTENER (service) |
|---|---|---|
| how work arrives | pushed in (an inbox fills) | pulled out (a caller asks) |
| shape | a bento walks the lifecycle FSM | a request comes in, a response goes out |
| state | owns no store; the bento is the state | owns a durable store; requests are stateless |
| lifetime | ephemeral -- runs while there is work | resident -- always on, parked on a socket |
| wake source | the bus / a file appearing | a connection on its listening socket |

The watcher is **push**: something drops work in, the watcher reacts. The listener is
**pull**: something wants an answer, the listener has it. Neither polls the other, and
neither archetype is more of a frood than the other -- they are two answers to two
different questions, "what happens to this work?" and "what is true right now?"

## Why a listener does not spin

An always-on service sounds like an always-running loop, and an always-running loop
sounds like a pegged core. It is neither. A listener parks at roughly 0% CPU when idle
because **"waiting" is a blocking syscall, not a loop.** It calls `accept` (or `poll`,
or a blocking read) and the kernel does not return until there is something to do. The
process is descheduled -- it consumes no cycles -- until a connection arrives, at which
point it is woken, handles the request, and blocks again.

This is where the two archetypes genuinely differ -- they wake differently, and that is the
point. The listener is **event-driven**: it blocks on `accept` and parks at ~0% idle CPU,
woken only when a request actually arrives. The watcher **polls**: it wakes on a bounded
interval, scans its inbox, handles whatever is new, and sleeps again. Polling is not parked,
but it is not a busy-wait either -- the interval keeps it from free-running, so the cost is a
cheap, bounded tick rather than a core burned asking "is there work yet?" whose answer is
almost always no. (A *bus*-consuming watcher would block on the consumer poll, closer to the
listener's pattern; the default filesystem-inbox watcher does not -- it sleeps and scans.)

## Semistate: the data is durable, the request is not

A listener is stateful and stateless at once, and the two words are about two different
things. Its **data** is persistent -- that is the point of a resident service that owns a
store. Its **request handling** is stateless: there is no session, no login step, no
server-side memory of who you are between calls. The credential rides every request (see
the credential envelope in the data contract), so each request stands alone and carries
everything needed to serve it.

That statelessness is not a minor convenience; it is the **horizontal-scale seam.** A
request that depends on nothing held in this particular process can be served by any
process with access to the store. Today the mesh runs at `nodes == 1` and a single
listener answers everything. Tomorrow it can run at `nodes == N` -- put more listeners in
front of the same durable store -- and *no protocol changes*, because nothing about a
request assumed there was only one of them. We do not build the N-node deployment now; we
decline to foreclose it, which costs nothing if the request handling is honestly
stateless from the start.

## Every loop blocks; every retry backs off

There is one operational rule that both archetypes obey, and it is the rule that keeps an
always-on service from becoming an always-burning one:

> No loop free-runs: it blocks on an event, waits a bounded interval, or backs off a retry.

The first half is the wake rule above -- a listener blocks on its socket, a watcher sleeps a
bounded interval; neither spins in a tight `is-there-work-yet?` cycle. The second half is
the failure case that bites in practice. A listener depends on things that can be down -- its store, the
bus, a discovery lookup. The naive reconnect is a `while not connected: connect()` loop,
and when the dependency is *durably* down that loop pegs a core doing nothing, on a
machine that is also the operator's laptop. So every reconnect and retry path uses bounded
backoff: it waits, longer each time up to a ceiling, between attempts. A dead dependency
costs a slow, quiet trickle of retries, not a hot loop. This is the listener equivalent of
the pipeline's `PARTIAL` discipline -- when the world is not ready, degrade quietly rather
than spin.

## Froodship: what a listener keeps, and what it drops

Both archetypes are built on the shared frood layer, and a listener keeps the parts that
make a thing a member of the mesh:

- **identity** -- it knows its own name and registers under it;
- **heartbeat** -- it reports that it is alive;
- **discovery** -- it can be found by the orchestrator;
- **emit** -- it can put events on the bus.

A listener **drops** the two things that belong to the watcher and not to it: the
**bento lifecycle FSM** (it does not walk work through states; it answers requests) and the
**watcher / inbox** (nothing is pushed into it). Those are not disabled or stubbed -- they
are simply not part of this archetype.

Liveness is **self-reported**, and that detail matters. A listener heartbeats via its own
emit sidecar -- the component closest to the truth of whether the service is actually up --
onto the shared `observability.events` topic, keyed by service name. It is never a
per-service topic (the fleet watches one stream, not a discovered set of them), and the
registry **does not fabricate** a service's liveness: absence of a heartbeat is absence of
a claim, not a synthesized "down" or "up." The thing that knows whether it is alive is the
thing that says so.

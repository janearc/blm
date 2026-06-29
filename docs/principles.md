# Big Little Mesh principles

## Contracts first; generate, don't hand-write

Big Little Mesh aims for as little hand-written code as possible -- including code written by
an agent. We define our contracts in protobuf and generate the code that speaks
them: Go and Python today, Rust the day we want it, all bound by the same
contracts.

This is deliberate, and it is old wisdom rather than novelty. Fifteen years ago
we wrote protobuf and adapted the generated code, and that was simply how serious
systems were built. We are doing the same thing.

The payoff is that one whole class of error stops being a matter of trust. A
contract is a hard boundary: if a message is not in the spec, Kafka and the schema
registry reject it, no matter how clever or careful the surrounding logic is.
Neither a human nor an agent can put a *malformed* message on the wire. What a
contract does not catch is a well-formed lie -- a message that is valid but carries
the wrong values; that is still on tests and review. The contract removes a class
of failure, not all of them.

So the surface you have to trust shrinks to two small, reviewable things: the
contract, and the bounded behavior hand-written on top of it. Contract changes go
through a diff that is reviewed and landed; schema-registry compatibility and buf
breaking-checks enforce it. Be as weird as you like in your own code -- you do not
get to change the environment without an approved diff.

## Containment, not trust

We do not trust the author of a change -- human or agent -- more than we trust any
coworker. Everyone makes mistakes; that is not a claim about AI, it is a claim
about people and computers alike. So the mesh is built so that trust is not
required: it bounds what any actor can break.

Two layers do this. **Contracts** protect the data plane -- a malformed message
cannot reach the wire, so no change can corrupt data or take down another service
by malforming what it emits. **Isolation** bounds the blast radius of the code
itself -- a service runs in a container, reads its secrets only from injected
references, and cannot touch the host's disk or another service's state. A broken
change can still exhaust memory or peg a core, and that can hurt the host and its
neighbors -- that failure mode is real. What it cannot do is leak a secret it was
never given, reach the disk, or silently corrupt another service's data. The
damage it can do is the loud, recoverable kind, not the silent, spreading kind.

That is what makes it possible to land -- and to trust -- code you have not read.
It is the same property that let thousands of engineers move fast on one
self-healing mesh: not because everyone was careful, but because the default blast
radius of any one change is small. This is not a promise that nothing can burn --
people take production down, ourselves included, and these controls do not change
that. What they buy is distance: there are many gates between one commit and a
fleet-wide outage, and clearing all of them takes reckless, uninformed confidence,
not an ordinary mistake. The ordinary mistake breaks the one thing you are working
on, loudly, and stops there. That is the bar that lets an agent be handed real
work -- not that nothing can go wrong, but that the everyday wrong is contained.

# blm principles

## Contracts first; generate, don't hand-write

blm aims for as little hand-written code as possible -- including code written by
an agent. We define our contracts in protobuf and generate the code that speaks
them: Go and Python today, Rust the day we want it, all bound by the same
contracts.

This is deliberate, and it is old wisdom rather than novelty. Fifteen years ago
we wrote protobuf and adapted the generated code, and that was simply how serious
systems were built. We are doing the same thing.

The payoff is that correctness stops being a matter of trust. A contract is a
hard boundary: if a message is not in the spec, Kafka and the schema registry
reject it, no matter how clever or careful the surrounding logic is. Neither a
human nor an agent can put a malformed message on the wire -- the freedom to
introduce that class of bug is simply not there.

So the surface you have to trust shrinks to two small, reviewable things: the
contract, and the bounded behavior hand-written on top of it. Contract changes go
through a diff that is reviewed and landed; schema-registry compatibility and buf
breaking-checks enforce it. Be as weird as you like in your own code -- you do not
get to change the environment without an approved diff.

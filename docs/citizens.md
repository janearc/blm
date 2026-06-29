# Citizens: the guaranteed interface

Every member of the mesh is a **citizen** -- a watcher or a listener (see
[services.md](services.md)), it does not matter which. Citizenship is what they share, and a
citizen is required to expose a small **guaranteed interface**: the good_citizen baseline,
made mandatory and machine-checkable. It is the minimum that lets the mesh know a thing is
alive, who it is, and what it speaks -- without reading its code or trusting its word.

## The guaranteed set

A citizen exposes at least:

- **`GET /health`** -- liveness. The existing convention; a citizen that does not answer here
  is not alive as far as the mesh is concerned.
- **identity** -- who-am-I: `service_name`, the declared `project` it binds to, and a
  `version`. The contract is `citizen.v1.Identity`.
- **a contract descriptor** -- what this citizen *emits*, *consumes*, and *serves*, each named
  by subject. The contract is `citizen.v1.ContractDescriptor`.

Liveness says it is up; identity says which project it is acting as; the descriptor says what
it speaks. Those three answer the only questions a peer or the orchestrator has to ask before
trusting a citizen to participate.

## Naming contracts by subject

The descriptor names contracts by **subject** -- the contract's RecordNameStrategy identity,
which is the fully-qualified protobuf message name (e.g. `observability.v1.ServiceHealthHeartbeat`).
That is deliberate: it is the same key the bus and the schema registry already use, so a claim
in the descriptor is not prose -- it is checkable against what is actually registered. A
citizen that claims to emit a subject the registry has never seen is making a claim that fails
verification, not one that quietly passes.

The split by direction is how a peer routes and how the mesh reasons about flow: a watcher
typically *emits* and *consumes* on the bus; a listener typically *serves* a request surface.
A citizen may do any combination -- the descriptor states which, per contract.

## Verified at register

The guaranteed set is not a style guide; it is an admission check. delightd is becoming a
`/register` broker for the mesh, and registration verifies that a citizen exposes this set and
that its descriptor claims check out before the citizen is admitted. A citizen that cannot say
who it is or what it speaks does not get to participate.

This is staged and additive. Defining and exposing the interface comes first; verification at
register comes with the broker; making registration mandatory -- retiring the static roster and
poll -- is the last step, not this one. Until then the guaranteed interface is the contract a
citizen is built against, and the thing the broker will check when it arrives.

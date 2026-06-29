# Citizens: the guaranteed interface

A **citizen** is a project that participates in the mesh, watcher or listener (see
[services.md](services.md)). Every citizen MUST provide the **guaranteed interface** defined
here: a fixed set of endpoints plus one publishing obligation that let the mesh identify it,
check that it is up, and learn what it speaks. The interface is the
[`good_citizen`](../citizen) library's baseline (mirrored in [Python](../python/good_citizen));
`citizen.v1` is its contract.

## blm and delightd

The interface spans two components, and the split between them is logical -- a matter of
convenience -- so it is worth stating what lives where:

- **blm** is the library and the contracts. `good_citizen` is the shared code every citizen
  builds on; the packages under `proto/` (including `citizen.v1`) are the contracts the mesh
  speaks; generated code reflects those contracts and yaml wires it to the hand-written
  behavior. blm defines what a citizen *is*. It is the mesh's set of foundational building
  blocks -- a busybox for service meshes.
- **delightd** is the orchestrator. It holds the roster, coordinates each citizen's ingress
  and egress, and (in the register campaign) brokers `/register`. delightd decides who is *on*
  the mesh.

This document describes the blm half: the interface a citizen MUST present. What delightd does
with that interface is delightd's to document.

## The guaranteed set

Every citizen MUST:

- **answer `GET /health`** -- liveness. A citizen that does not answer is treated as down.
- **answer an identity request** -- `service_name`, the declared `project` it binds to, and a
  `version`. The contract is `citizen.v1.Identity`.
- **answer a contract-descriptor request** -- the contracts it `emits`, `consumes`, and
  `serves`, each named by subject. The contract is `citizen.v1.ContractDescriptor`.
- **emit metrics** -- a citizen MUST publish metrics to a topic the bus knows about: its own
  topic registered with the schema registry, or an existing one it reuses. The format and
  cadence are the citizen's choice; the obligation is that it publishes. Metrics carried as a
  bus contract appear in the descriptor's `emits` like any other emitted subject.

Health reports that it is up, identity reports which project it acts as, the descriptor reports
what it speaks, and metrics report what it is doing. These are the inputs the mesh needs to
treat a process as a citizen.

## Naming contracts by subject

The descriptor names each contract by **subject** -- its RecordNameStrategy identity, the
fully-qualified protobuf message name (e.g. `observability.v1.ServiceHealthHeartbeat`). This is
the same key the bus and the schema registry use, so a descriptor entry is checkable: a claimed
subject either matches a registered contract or it does not. delightd verifies the claims
against the registry rather than taking them on trust.

The direction split lets a peer route and the mesh reason about flow. A watcher typically
`emits` and `consumes`; a listener typically `serves`. A citizen MAY do any combination; the
descriptor states which, per contract.

## Verified at register

The guaranteed set is an admission check, not a convention. delightd's `/register` (the
register campaign) verifies that a citizen provides the set and that its descriptor claims
resolve against the registry before admitting it.

The campaign is staged and additive. The interface is defined and implemented first;
`/register` verifies it next; making registration mandatory -- retiring the static roster and
poll -- is the final step. Until then `citizen.v1` is the contract a citizen is built against,
and the set `/register` will check.

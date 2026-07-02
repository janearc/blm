# Contract ownership

Every protobuf package on the mesh has exactly one owning repository. The owner's
`.proto` files are the source of truth; every other repository vendors from the owner
and regenerates. The owner's CI runs the authoritative `buf breaking` check for its
packages — a breaking change is caught where the contract lives, not where it lands.

## Owned by big-little-mesh

- `frood.v1` — the frood service surface. Consumers (delightd, magpie via generated
  clients) vendor from here.
- `bento.v1`, `auth.v1`, `model.v1`, `dataprovider.v1`, `sidecar.v1` — the mesh
  substrate packages, defined under `proto/`.

## Vendored here (owned elsewhere)

- `registry.v1` — owned by **delightd** (see delightd `docs/contract-ownership.md`).
  big-little-mesh vendors it for the register-client surface and regenerates; it does
  not edit it. A change to `registry.v1` starts as a delightd PR.

## Open

- `observability.v1` — ownership floats between this repo and kafka-svc (issue 77);
  this document deliberately does not claim it. When that issue is decided, the
  package moves to one of these two lists.

## Why this document exists

Recorded 2026-07-02 as the pilot prerequisite of ADR-0001 (the coding-process gates):
a schema-breaking gate needs one source of truth to diff against, so package ownership
is pinned explicitly instead of living in commit-message archaeology.

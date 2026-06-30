# proto/

These are Big Little Mesh's contracts: the single source of truth from which Go, Python, Rust,
and Swift are generated (see `buf.gen.yaml`), never hand-written.

Almost everything here is **Big Little Mesh-owned** — `frood/` (the universal frood interface),
`bento/`, `observability/`, `model/`, `sidecar/`, `auth/`, `dataprovider/`. One directory is
**vendored** from another repo, and the distinction matters because a vendored contract is a copy
that must stay byte-identical to its source — drift is a bug.

## `registry/` — vendored from delightd

`registry/v1/register.proto` is a **vendored copy** of delightd's `/register` broker wire,
owned upstream at `~/work/delightd/proto/registry/v1/register.proto`. delightd is the registry
broker; it owns the register protocol. Big Little Mesh vendors the copy so the Python
register-client (`python/frood/register.py`) can build a `registry.v1.RegisterRequest` and speak
the wire — the same generate-at-build way delightd vendors `frood.v1` *from here*.

Only `register.proto` is vendored (the wire the client speaks), not delightd's full `registry.v1`
(its project taxonomy, bus events, and service facets stay delightd's and are not needed here).
`register.proto` imports `frood/v1/frood.proto`, which resolves **locally** — `frood.v1` is
Big Little Mesh's own, so the vendored register wire and the interface it references meet here
without either repo depending on the other's module.

**Keep it byte-identical to delightd's source.** A change to the register wire is made in delightd
and re-vendored here; editing this copy in place would fork a contract delightd owns. To re-sync:

```sh
cp ~/work/delightd/proto/registry/v1/register.proto proto/registry/v1/register.proto
buf generate   # regenerate gen/{go,python}/registry from the proto
```

### Why this mirrors delightd's `frood/` vendor

It is the same split, in the other direction: delightd vendors `frood.v1` from Big Little Mesh
(the interface every frood implements is a Big Little Mesh concept), and Big Little Mesh vendors
`registry.v1`'s register wire from delightd (the broker protocol is delightd's). Each repo owns
its own contract and vendors the byte-identical copy of the other's where the two must meet — a
cross-repo buf-module dependency is heavier than either side needs.

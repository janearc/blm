# dataprovider.v1 — the mesh data contract

`DataProvider` is the mesh's data contract: the protocol *allows for* an append-only,
immutable cell store, modeled on Uber's Schemaless — the *interface*, not the distributed
system. Any service that satisfies this contract is a DataProvider; what it stores
underneath, and how strictly it enforces immutability, is its business.

## The cell model

The smallest entity is a **cell**: a JSON value (immutable in a faithful provider),
addressed and versioned by three coordinates.

- `row_key` — the entity identifier, a UUID.
- `column` — the field within that row.
- `ref_key` — the version. The **latest** cell for a `(row_key, column)` is the one
  with the highest `ref_key`.

A faithful provider never mutates a cell once written. A new value for `(row_key, column)`
is a new cell at a higher `ref_key`; the old cell stays exactly as it was. The store only
ever grows. The body is a `google.protobuf.Struct` — arbitrary JSON — so cells are
queryable, not opaque blobs.

## The four operations

| op | does |
|---|---|
| `Get(row_key, column, ref_key)` | returns one specific cell version |
| `GetLatest(row_key, column)` | returns the highest-`ref_key` cell for that pair |
| `Put(row_key, column, ref_key, body)` | appends a cell |
| `Query(index, predicates)` | returns cells matching a secondary-index lookup |

Reads return a wrapper (`GetResponse` / `GetLatestResponse`) carrying the `cell` and a
`found` flag. A miss is `found=false` with no cell — a successful call, not an error. The
behavior the protocol is shaped for, and a faithful provider upholds:

- **Append-only.** `Put` adds a cell; it does not overwrite one. There is no delete —
  immutability is the point, so nothing is removed from the contract surface.
- **Immutability on collision.** A provider that enforces immutability rejects a `Put` at
  an existing `(row_key, column, ref_key)` whose body differs (recommended for Schemaless
  fidelity); re-`Put`ting the identical cell is a no-op.
- **Idempotent writes.** The caller supplies `ref_key`, so re-issuing the same
  `Put(row_key, column, ref_key, body)` adds nothing. A retry is safe.
- **Eventually-consistent index.** `Query` reads a secondary index that trails the
  append log. A cell that was just `Put` may not be visible to `Query` yet; a `Get` of
  its coordinates always is.

## The query path — "request keys with meta"

`Query` is not a scan. You define a **secondary index** over the cells' JSON fields, and
then ask for the keys whose indexed fields satisfy a set of `predicates`. The response is
the matching cells. `shard_hint` is optional and **provisional** — an implementation-specific
routing hint, not a contract guarantee, and it may move to a transport header later;
Schemaless mandates a shard key on a query so it can route to a partition, this contract
does not, because partitioning is the implementer's concern, not the wire's. `limit` bounds
the result set, and `next_page_token` is reserved for pagination — no behavior yet, but the
field is claimed so `Query` is not locked into a single page.

## How to implement the contract

To be a DataProvider in the mesh, a service must:

1. **Honor the cell coordinates and append semantics.** A `(row_key, column, ref_key)`
   triple addresses a cell; honor caller-supplied `ref_key` and do not silently re-version.
   Enforcing immutability — rejecting a `Put` at existing coordinates whose body differs —
   is recommended for Schemaless fidelity.
2. **Serve `Get` / `GetLatest` consistently.** `GetLatest` returns the highest `ref_key`
   present for the pair. A read of a written cell never lies; a miss is `found=false`.
3. **Maintain at least one secondary index** and answer `Query` against it. Eventual
   consistency is allowed and expected; silently dropping writes from the index is not.
4. **Keep partitioning private.** Sharding, if any, lives below the contract. The wire
   exposes `shard_hint` as a routing courtesy, never a requirement.
5. **Validate credentials per your policy.** Every request carries opaque `auth.v1`
   credentials; the wire interprets none of them. Decide what an absent credential
   (`UNSPECIFIED`) means in your deployment — see *Divergence from Schemaless* below.

What the contract deliberately does *not* dictate: how cells are stored, how the index is
built, whether the thing is one process or a fleet. That is the Schemaless lesson — pin
the interface, leave the distributed system to the implementer.

## Transport, errors, and namespace

- **Transport.** This is a descriptor-only interface: it generates message types, not gRPC
  stubs. The mesh carries it as protojson-over-HTTP via the sidecar, not gRPC.
- **Errors.** An implementer signals failure with the HTTP status code, per the mesh provider
  convention (`400` malformed request, `503` unavailable/busy — retryable, `500` provider
  failure); the body is `{"error": "..."}`. A missing cell is *not* an error — it is
  `found=false` on a `200`.
- **Namespace.** `namespace` scopes a logical store / keyspace: cells in different namespaces
  share no `(row_key, column, ref_key)` space.

## Divergence from Schemaless

This contract is a deliberate, faithful read of Schemaless — checked against Uber's
published design and against the open reimplementations (`go-schemaless`, `shameless`).
Where it diverges, it diverges on purpose.

- **Faithful to the cell model.** `(row_key, column, ref_key) → immutable JSON cell`,
  append-only, latest = highest `ref_key`, queried through an index over the JSON fields.
  That is Schemaless, intact.
- **Cleaner than the reimplementations.** We model the *interface*, not the distributed
  system, so we drop the sharding operations the clones leaked up into the API
  (`PartitionRead`, `FindPartition`). Partitioning is an implementer's concern; it does not
  belong on the wire.
- **The one explicit divergence — auth.** 2016 Schemaless had no in-protocol auth.
  Back-end inter-service calls ran on *network trust*: inside the mesh meant trusted,
  effectively root. (User- and policy-level auth was a *separate* service, "Charter" — not
  inter-service auth; don't conflate the two.) We diverge by carrying an opaque per-request
  credential (`auth.v1`) on every call, because a 2026 mesh should not be
  root-if-you-can-ping-it. The zero value (`UNSPECIFIED` — no credential) *is* the old
  network-trust mode: the same axis, one end of it.
- **The seam, not the system.** Today the credential is opaque pass-through, validated by a
  stub. The real validator is `blm/libauth`, built when something forces it — e.g. when
  `intruder` connects in and starts writing files. The OAuth IdP is GitHub today, swappable
  to Sign in with Apple by configuration, not by changing this contract.

**The honest admission.** This is a 2026 revival of an abandoned protocol; as far as anyone
can tell, the author is the only person running Schemaless on Earth. And the part that has
to be loud: **carrying credentials on the wire like this is the wrong call the instant
anyone but the operator is on the network.** At n=1 it is fine. This is a *seam* — a place
to drop real auth when it's needed — not security. Do not mistake it for security.

## Attribution

Modeled on Uber's Schemaless, the append-only datastore described in:

- [Designing Schemaless, Uber Engineering's Scalable Datastore Using MySQL](https://www.uber.com/us/en/blog/schemaless-part-one-mysql-datastore/)
- [The Architecture of Schemaless, Uber Engineering's Trip Datastore Using MySQL](https://www.uber.com/us/en/blog/schemaless-part-two-architecture/)

If you know how to get shit out of schemaless, we can be friends.

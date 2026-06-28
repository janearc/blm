# dataprovider.v1 — the mesh data contract

*If you know how to get shit out of schemaless, we can be friends.*

**DataProvider is a neutral data layer: an append-only, immutable cell store that does not
care what you talk to it with.** Hand it cells, ask for cells, present whatever credential
your deployment uses — the protocol carries that credential without reading a byte of it.
It takes no opinion on your auth, your storage, or your use case. That is the entire pitch.

It is modeled on the **accessor libraries** for Uber's Schemaless — the client interface you
program against — and it is explicitly **not** a global datastore. We took the shape of the
API, not the distributed system behind it.

One thing, said once: this runs for a single operator, and at `nodes == 1` that is exactly
right. Everything below is written for that reality.

## The cell model

The smallest entity is a **cell**: a JSON value, addressed and versioned by three
coordinates.

- `row_key` — the entity identifier, a UUID.
- `column` — the field within that row.
- `ref_key` — the version. The **latest** cell for a `(row_key, column)` is the one with
  the highest `ref_key`.

A faithful provider never mutates a cell once written: a new value for `(row_key, column)`
is a new cell at a higher `ref_key`, and the old one stays exactly as it was. The store only
grows. The `body` is an arbitrary JSON **object** (`google.protobuf.Struct`), bounded by
what marshals in one bus message — its fields are what `Query` indexes. (A body larger than
one bus message is a future concern; a field number is reserved for a chunk or blob-ref so
adding it later is not a breaking change.)

## The four operations

| op | does |
|---|---|
| `Get(row_key, column, ref_key)` | returns one specific cell version |
| `GetLatest(row_key, column)` | returns the highest-`ref_key` cell for that pair |
| `Put(row_key, column, ref_key, body)` | appends a cell |
| `Query(index, predicates)` | returns cells matching a secondary-index lookup |

Reads return a wrapper (`GetResponse` / `GetLatestResponse`) carrying the `cell` and a
`found` flag; a miss is `found=false`, a successful call rather than an error. The behavior
the protocol is shaped for, and a faithful provider upholds:

- **Append-only.** `Put` adds a cell; it does not overwrite one. There is no delete.
- **Immutability on collision.** A provider that enforces immutability rejects a `Put` at an
  existing `(row_key, column, ref_key)` whose body differs (recommended for Schemaless
  fidelity); re-`Put`ting the identical cell is a no-op.
- **Idempotent writes.** The caller supplies `ref_key`, so re-issuing the same `Put` adds
  nothing. A retry is safe.
- **Eventually-consistent index.** `Query` reads a secondary index that trails the append
  log; a just-written cell may not be in `Query` yet, but a `Get` of its coordinates always
  is.

## The query path — "request keys with meta"

`Query` is not a scan. You define a **secondary index** over the cells' JSON fields, then ask
for the keys whose indexed fields satisfy a set of `predicates`; the response is the matching
cells. `limit` bounds the result set, and `next_page_token` is reserved for pagination — no
behavior yet, but the field is claimed so `Query` is not locked into a single page.

`shard_hint` is optional and provisional. blm is a `nodes == 1` mesh: we ignore sharding
entirely and keep the field to pretend we care. It is there for Schemaless fidelity and is a
no-op for us.

## Auth: the layer carries it, it does not run it

- The credential field is **opaque**. The protocol interprets nothing — `type` is a routing
  hint, the payload is bytes whose meaning belongs to the consumer.
- OAuth is **not mandatory** and **not this layer's job.** The door is Cloudflare Access:
  nothing reaches the mesh without passing the gateway. The data layer's concern is the
  finer, per-record capability — who may touch *this* cell — not whether you were let in the
  building.
- An absent credential (`UNSPECIFIED`) is the network-trust mode. At `nodes == 1` that is a
  fine default; the field is present so you can tighten policy later without a contract
  change.

## How to implement the contract

To be a DataProvider in the mesh, a service must:

1. **Honor the cell coordinates and append semantics.** A `(row_key, column, ref_key)` triple
   addresses a cell; honor caller-supplied `ref_key` and do not silently re-version. Enforcing
   immutability — rejecting a `Put` at existing coordinates whose body differs — is recommended
   for Schemaless fidelity.
2. **Serve `Get` / `GetLatest` consistently.** `GetLatest` returns the highest `ref_key` present
   for the pair. A read of a written cell never lies; a miss is `found=false`.
3. **Maintain at least one secondary index** and answer `Query` against it. Eventual consistency
   is allowed and expected; silently dropping writes from the index is not.
4. **Keep partitioning private.** Sharding, if any, lives below the contract. The wire exposes
   `shard_hint` as a routing courtesy, never a requirement.
5. **Validate credentials per your policy.** Every request carries opaque `auth.v1` credentials;
   the wire interprets none of them. Decide what an absent credential means in your deployment.

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

Yes — we track divergences from a dead 2016 protocol that, as far as anyone can tell, never
ran outside Uber. We do it anyway, because the shape is good and the discipline is cheap.

- **Faithful to the cell model.** `(row_key, column, ref_key) → immutable JSON cell`,
  append-only, latest = highest `ref_key`, queried through an index over the JSON fields.
  Intact.
- **Cleaner than the reimplementations.** We model the *interface*, not the distributed system,
  so we drop the sharding operations the clones (`go-schemaless`, `shameless`) leaked up into
  the API (`PartitionRead`, `FindPartition`). Partitioning does not belong on the wire.
- **The one explicit divergence — auth.** 2016 Schemaless had no in-protocol auth: inter-service
  calls ran on network trust, and user/policy auth lived in a *separate* service ("Charter") —
  not inter-service auth, don't conflate them. We carry an opaque per-request credential instead,
  because a 2026 mesh should not be root-if-you-can-ping-it.
- **The seam, not the system.** The credential is opaque pass-through today, validated by a stub;
  the real validator is `blm/libauth`, built when something forces it (e.g. when `intruder`
  connects in and starts writing files). The IdP is GitHub today, swappable to Sign in with Apple
  by configuration, not by changing this contract.

## Attribution

Modeled on Uber's Schemaless, the append-only datastore described in:

- [Designing Schemaless, Uber Engineering's Scalable Datastore Using MySQL](https://www.uber.com/us/en/blog/schemaless-part-one-mysql-datastore/)
- [The Architecture of Schemaless, Uber Engineering's Trip Datastore Using MySQL](https://www.uber.com/us/en/blog/schemaless-part-two-architecture/)

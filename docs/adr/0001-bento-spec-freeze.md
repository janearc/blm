# ADR 0001 — Freezing the bento spec (the 0.5 line)

## Status

Accepted, 2026-06-23. The spec is frozen; the code is not shipped. Release path:
**0.4.1** — move every pipeline onto the good-citizen surface and kick the tires (Kafka
is still dry) — then **0.5** once the contract is proven on a live bus. "Frozen spec"
does not mean "shipped."

## Context

A bento is the unit of work; a banchan is an irreducible *element* of one, not a step
(see `docs/pipelines.md`). Before every pipeline moves onto good-citizen, the bento
contract has to stop moving: adopters need a stable target, and a contract changed after
adoption is an outage.

The spec is grounded in the one bento that already works on disk — paling's. A paling
bento is a directory (`raw_data/`, `schema/`, `preflight/`, `acceptance/`, `output/`, …)
with a `schema.json` of `{archetype, routing}`, walked through stages that each read the
directory and write back. The `proto/bento/v1` contract is that bento lifted to the wire.

Before freezing, the contract was pressure-tested against the unbuilt research pipelines
(sintra/grackle text+video/image, cardinal commodity text, speedy near-realtime,
mackerel/intruder multi-pipeline choreography). Those are **direction, not requirements**
— they say where the substrate must be *able* to go. Finding: nothing in them breaks the
base, but three things push on it, and the freeze must leave room without committing.

## Decision

### The contract (frozen)

- `Bento{ id, name, kind, state, root_path, schema_json, prompt, banchans[] }`. `kind` is
  the archetype — the bento's type.
- `Banchan{ guid, name, kind, location, assets[] }` — an element of the bento.
- `BanchanAsset{ kind, location }`, `kind ∈ { PRE_FLIGHT, ACCEPTANCE_TEST,
  COMPATIBILITY_TEST }` — the checks a banchan carries.

The lifecycle FSM and the food-themed states are governed by `docs/pipelines.md`; this
ADR governs the *shape*.

### `schema_json` is versioned and carries the recipe

The richest real push comes from already-scaffolded code, not speculation: grackle and
sintra carry tuned per-stage parameters (resolution, steps, sampler, guidance, model
choice), selectable named recipes, and a record of caller overrides — far more than
paling's stage→backend `routing`. That config is semi-structured and per-archetype;
proto-typing every archetype's knobs would be the wrong move.

Decision: `schema_json` carries `{ schema_version, archetype, routing, recipe,
caller_overrides }` and is **versioned**. The recipe grows there, behind a version,
without touching the proto. This also defers the `kind`-vs-`archetype` duplication:
`kind == archetype` today, and a later `schema_version` can reconcile it. grackle,
sintra, and cardinal are the next adopters — this is the seam they need.

### Defensive specification: reserve, don't define

We reserve slots for things we can see coming but will not define yet, so a later need
lands without renumbering or breaking the wire. Field numbers and enum values are
forever; reserving is cheap, repainting is not.

- Bento states `CHEW` / `DIGEST` / `SPOILED` are already reserved.
- Reserve `BanchanAsset.kind` values (plus numeric gaps) for produced-artifact / modality
  kinds — the research produces video/image/audio/text, while today's enum is
  test-oriented only.
- Reserve a **provenance** concept: owner-supplied vs pipeline-generated banchans. paling
  already splits `anchors/owner` from `anchors/paling`, and the choreography pipelines
  generate banchans mid-flow, so this generalizes across the whole future.
- Reserve a **composition-itinerary** field on `Bento`, declared with **no execution
  semantics**. This is the inter-pipeline "where does this go next" notion — distinct
  from intra-bento `routing` — that mackerel/intruder need. Its mechanism (choreography
  vs a non-pipeline orchestrator) is **held**: mackerel's own design flags its central
  coordinator as a possible misuse of the mesh. v0.5 reserves the slot and defines
  nothing; the mechanism is a v0.6 decision.

### No opaque extension map

We do **not** add a free-form key/value "ext" field to absorb future needs. Un-typed data
on the wire is the opposite of the contract being the guardrail (`docs/principles.md`):
the contract could guarantee nothing about it, and it rots into a dumping ground. proto3
lets typed fields be added later without breaking compatibility, so a future need gets a
*typed* field when it is real — a small proto change per need, which is the price of
keeping off-spec data off the wire.

### Batch-scoped language

The spec asserts its invariants for **batch mode** only, never universally. speedy is a
second processing mode — near-realtime, *not* streaming: a session is a bento, a segment
is a banchan, but the batch guarantees are inverted (the session is stateful, results are
partial and revisable, a segment's asset is appended/revised rather than written once).
speedy will land later in its own package; if v0.5 asserted batch invariants as universal
truths, speedy would contradict the frozen spec and force a reopen.

So these are stated as batch-mode conventions in this spec and in the contract comments,
never as universal guarantees:

- a bento terminates in `DONE` / `PARTIAL` / `FAILED` (batch mode);
- a banchan asset's `location` points to an artifact produced once (batch mode);
- a citizen is stateless between events (batch mode);
- the on-disk directory layout is a **per-archetype convention** that good-citizen
  scaffolds — not a contract guarantee. grackle/lloyd/liarbird already use a leaner layout
  than paling's full tree, which proves the layout is per-archetype, not universal.

The fields do not change; only the prose carries a scope. The near-realtime mode adds its
own semantics in its own package without making these words wrong.

## Consequences

- grackle / sintra / cardinal can adopt now — their recipe richness rides in versioned
  `schema_json`.
- speedy / mackerel / intruder have reserved room (the itinerary slot, the batch-scoped
  language) without v0.5 committing to a mechanism that is still held.
- The two ways to paint into a corner are both closed: burning a field number on the
  wrong thing (closed by reserve-don't-define) and asserting a universal you later must
  violate (closed by batch-scoping).
- Cost: a small typed-field proto PR per future need, instead of a junk-drawer now.
  Accepted.

## Not covered here

The producer/consumer reference pair (`dummy-producer` + `dummy-consumer`), the bento
repository (`blm/pipelines/bentos`), and the canary cadence are *implementation that
consumes this spec*. They are tracked in the epic, not in this ADR.

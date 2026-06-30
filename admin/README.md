# admin

`admin` is frood's **provisioning surface**: the operations that make the bus ready to use, as
tracked, idempotent Go you run rather than hand-typed `kafka-topics` / `curl` commands that
drift. A plain frood only *produces* and *consumes*; the bus owner also has to *create the
topics* and *register the schemas* the fleet agreed on. Those administrative steps live here.

The fleet runs with broker topic auto-create **off** and froods registering with delightd
*before* they have produced anything — so neither topics nor schemas can be left to appear on
their own. Both have to exist up front, from a declared set, created the same way every boot.

## What's here

| File | Declares | Ensures | Run by |
|------|----------|---------|--------|
| `topics.go` | `FleetTopics()` — the fleet's Kafka topics | `EnsureTopics()` | `cmd/provision-topics` |
| `subjects.go` | `FleetSubjects()` — the contract schemas in the Schema Registry | `EnsureSubjects()` | `cmd/provision-schemas` |

The `Fleet*()` function in each is the **single source of truth** for what the fleet expects to
exist; the `Ensure*()` function makes it so.

## How these are built (the shape every provisioner here follows)

- **Self-contained.** Each `Ensure*` opens (and closes) its own short-lived client — a Kafka
  admin client for topics, an HTTP client for the Schema Registry. A provisioner does not share
  a producer's or consumer's connection.
- **Idempotent.** An already-existing topic, or an already-registered identical schema, is
  success — so the provisioner is safe to run on every boot.
- **Fail-closed.** A real failure (or a missing broker / registry URL) is returned loudly, never
  a silent no-op. A topic or subject that quietly failed to provision would surface later as a
  mystery produce error or a `verifyContracts` 422 at register time — far from its cause.

## Why subjects are provisioned ahead of producing

delightd's `/register` checks that each contract subject a frood claims to speak already exists
in the Schema Registry. But a frood registers *before* it emits its first event — and emitting
is what would otherwise lazily register the schema. So `EnsureSubjects` registers the contract
schemas up front, under the same RecordNameStrategy subjects (and the same Confluent wire) the
producer uses, so the provisioned subject and the produced one are the same registration — it
just exists before the first register instead of after the first produce.

## Ownership

`admin` is the superset the bus owner (kafka-svc) calls; a leaf frood never has to. Keeping it as
idempotent library code here — rather than runbook commands — is what keeps provisioning tracked
and reproducible instead of drifting away from the contracts.

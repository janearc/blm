// Package bentoproto embeds the canonical bento.v1 contract source so a service (the
// emit sidecar) can register the schema with the Schema Registry at runtime. This is
// the same bento.proto buf generates from -- embedded in place, not a vendored copy,
// so the registered schema cannot drift from the contract.
package bentoproto

import _ "embed"

// Schema is the PROTOBUF schema text registered under the
// bento.v1.BentoLifecycleEvent subject (RecordNameStrategy).
//
//go:embed bento.proto
var Schema string

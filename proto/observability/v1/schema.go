// Package observabilityproto exposes the observability.v1 .proto source text for
// Confluent Schema-Registry registration. The schema travels with frood
// (Big Little Mesh is its canonical home), so the registered wire schema and the generated
// Go bindings come from one place rather than a vendored copy.
package observabilityproto

import _ "embed"

// Schema is the raw observability.proto, embedded for Schema-Registry
// registration (RecordNameStrategy subjects, e.g. observability.v1.ServiceHealthHeartbeat).
//
//go:embed observability.proto
var Schema string

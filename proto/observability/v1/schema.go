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

// The RecordNameStrategy Schema-Registry subjects for the observability records, as the ONE
// canonical home for these strings: a subject is the fully-qualified protobuf message name, and
// both the producer (frood.Heartbeat) and the provisioner (admin.FleetSubjects) must name the
// same one. Co-locating the constant with the schema it registers under means a proto message
// rename changes the subject in a single place instead of silently desyncing bare literals
// scattered across the producer, the provisioner, and their tests.
const (
	SubjectServiceHealthHeartbeat = "observability.v1.ServiceHealthHeartbeat"
	SubjectTokenBurnEvent         = "observability.v1.TokenBurnEvent"
)

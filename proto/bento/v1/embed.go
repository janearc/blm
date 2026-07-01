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

// SubjectBentoLifecycleEvent is the RecordNameStrategy subject for the bento lifecycle event, as
// the ONE canonical home for the string: the sidecar produces under it and admin.FleetSubjects
// provisions it, and both must name the same subject. Co-locating it with the schema it registers
// under means a message rename changes the subject in one place, not silently across scattered
// literals.
const SubjectBentoLifecycleEvent = "bento.v1.BentoLifecycleEvent"

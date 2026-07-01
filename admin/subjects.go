// subjects.go is frood's Schema-Registry provisioning surface -- the schema sibling of topics.go.
// Where EnsureTopics declares the fleet's Kafka topics, EnsureSubjects declares the contract
// SCHEMAS that must exist in the Confluent Schema Registry before any frood registers.
//
// Why provision ahead of emit: delightd's /register runs verifyContracts, which checks that each
// subject a frood claims to speak is already registered (SubjectExists). But a frood registers
// with delightd BEFORE it has produced its first event -- and producing is what would otherwise
// lazily register the schema (see emit.Publisher.schemaID). So the subjects have to be registered
// explicitly, ahead of time, the same run-every-boot way topics are. Without this, the very first
// register 422s on a subject nothing has emitted yet.
package admin

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	bentoproto "github.com/janearc/big-little-mesh/proto/bento/v1"
	observabilityproto "github.com/janearc/big-little-mesh/proto/observability/v1"
)

// SubjectSpec declares one Schema-Registry subject: the RecordNameStrategy subject name (the
// fully-qualified protobuf message name, e.g. "observability.v1.ServiceHealthHeartbeat") and the
// .proto source text registered under it.
type SubjectSpec struct {
	Subject    string
	SchemaText string
}

// EnsureSubjects registers each spec's schema in the Schema Registry at schemaRegistryURL,
// idempotently: re-registering an identical schema returns the existing id, so this is safe to
// run every boot. A registration failure is returned (fail-closed) -- a subject that did not
// register would 422 every frood register that depends on it, so a provisioner that could not
// register must say so loudly rather than let the gap surface later as a mystery register failure.
//
// Like EnsureTopics, it is self-contained: it owns a short-lived HTTP client and does the
// Schema-Registry POST itself rather than borrowing emit.Publisher's producer-time registration --
// a provisioner does not share the producer's client. The wire is identical to what
// emit.Publisher.registerSchema produces; a provisioned subject and a producer-registered one are
// the same registration, provisioning just guarantees it exists before the first produce.
func EnsureSubjects(ctx context.Context, schemaRegistryURL string, specs ...SubjectSpec) error {
	if schemaRegistryURL == "" {
		return fmt.Errorf("no schema registry url configured")
	}
	httpc := &http.Client{Timeout: 10 * time.Second}
	for _, s := range specs {
		if err := registerSubject(ctx, httpc, schemaRegistryURL, s); err != nil {
			return fmt.Errorf("register subject %q: %w", s.Subject, err)
		}
	}
	return nil
}

// registerSubject POSTs one schema under its RecordNameStrategy subject. The wire matches
// emit.Publisher.registerSchema: {"schemaType":"PROTOBUF","schema":<text>} to
// /subjects/{subject}/versions, the Confluent SR REST shape. The schema's import of
// google/protobuf/timestamp needs no explicit references -- Confluent bundles the well-known
// types -- which is why this single POST registers the whole observability.proto unmodified.
func registerSubject(ctx context.Context, httpc *http.Client, srURL string, s SubjectSpec) error {
	body, err := json.Marshal(map[string]string{"schemaType": "PROTOBUF", "schema": s.SchemaText})
	if err != nil {
		return err
	}
	url := fmt.Sprintf("%s/subjects/%s/versions", strings.TrimRight(srURL, "/"), s.Subject)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, strings.NewReader(string(body)))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/vnd.schemaregistry.v1+json")
	resp, err := httpc.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("registry returned %d: %s", resp.StatusCode, strings.TrimSpace(string(b)))
	}
	return nil
}

// FleetSubjects is the contract-schema set provisioned ahead of registration -- the schema sibling
// of FleetTopics. Today it is the observability.v1 records that ride observability.events: the
// heartbeat every frood MUST emit (delightd's /register hard-requires this subject) and the
// token-burn event -- plus the bento lifecycle event, which a watcher frood (magpie) declares it
// emits at register time, so its subject must exist too. Each subject string comes from the
// canonical proto-package const -- the SAME const its producer emits under (frood.Heartbeat, the
// sidecar) -- so the provisioned subject and the produced subject cannot drift. Add a subject here
// when a new contract becomes a register-time requirement.
func FleetSubjects() []SubjectSpec {
	return []SubjectSpec{
		{Subject: observabilityproto.SubjectServiceHealthHeartbeat, SchemaText: observabilityproto.Schema},
		{Subject: observabilityproto.SubjectTokenBurnEvent, SchemaText: observabilityproto.Schema},
		{Subject: bentoproto.SubjectBentoLifecycleEvent, SchemaText: bentoproto.Schema},
	}
}

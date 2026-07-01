package admin

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestEnsureSubjects_RegistersEachSubject drives EnsureSubjects against a fake Schema Registry
// and asserts it POSTs each subject under the Confluent wire shape.
func TestEnsureSubjects_RegistersEachSubject(t *testing.T) {
	var paths []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.URL.Path)
		// the body is the Confluent SR registration shape: schemaType + the proto text.
		b, _ := io.ReadAll(r.Body)
		var payload map[string]string
		if err := json.Unmarshal(b, &payload); err != nil {
			t.Errorf("body is not json: %v", err)
		}
		if payload["schemaType"] != "PROTOBUF" {
			t.Errorf("schemaType = %q, want PROTOBUF", payload["schemaType"])
		}
		if payload["schema"] == "" {
			t.Errorf("schema text must not be empty")
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/vnd.schemaregistry.v1+json" {
			t.Errorf("content-type = %q", ct)
		}
		w.Write([]byte(`{"id":7}`))
	}))
	defer srv.Close()

	err := EnsureSubjects(context.Background(), srv.URL,
		SubjectSpec{Subject: "observability.v1.ServiceHealthHeartbeat", SchemaText: `syntax = "proto3";`},
		SubjectSpec{Subject: "observability.v1.TokenBurnEvent", SchemaText: `syntax = "proto3";`},
	)
	if err != nil {
		t.Fatalf("EnsureSubjects: %v", err)
	}
	if len(paths) != 2 ||
		!strings.Contains(paths[0], "/subjects/observability.v1.ServiceHealthHeartbeat/versions") ||
		!strings.Contains(paths[1], "/subjects/observability.v1.TokenBurnEvent/versions") {
		t.Fatalf("unexpected subject POSTs: %v", paths)
	}
}

// TestEnsureSubjects_PropagatesRegistryError pins fail-closed: a registry rejection is returned,
// not swallowed -- a subject that did not register would 422 every dependent frood register.
func TestEnsureSubjects_PropagatesRegistryError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnprocessableEntity)
		w.Write([]byte(`{"error_code":42201,"message":"invalid schema"}`))
	}))
	defer srv.Close()
	err := EnsureSubjects(context.Background(), srv.URL, SubjectSpec{Subject: "x.v1.Y", SchemaText: "bad"})
	if err == nil {
		t.Fatal("expected an error from a 422 registry response")
	}
	if !strings.Contains(err.Error(), "x.v1.Y") {
		t.Errorf("error should name the subject that failed: %v", err)
	}
}

// TestEnsureSubjects_RejectsEmptyURL keeps the misconfiguration loud rather than silently doing
// nothing (a no-op provisioner would let the gap surface as a register failure later).
func TestEnsureSubjects_RejectsEmptyURL(t *testing.T) {
	if err := EnsureSubjects(context.Background(), "", SubjectSpec{Subject: "x", SchemaText: "y"}); err == nil {
		t.Fatal("expected an error for an empty schema registry url")
	}
}

// TestFleetSubjects_IncludesHeartbeatWithSchema guards the one subject delightd's /register
// hard-requires, with non-empty embedded schema text.
func TestFleetSubjects_IncludesHeartbeatWithSchema(t *testing.T) {
	var found bool
	for _, s := range FleetSubjects() {
		if s.Subject == "observability.v1.ServiceHealthHeartbeat" {
			found = true
			if s.SchemaText == "" {
				t.Error("heartbeat subject has empty schema text (the embedded proto did not load)")
			}
		}
	}
	if !found {
		t.Fatal("FleetSubjects must include observability.v1.ServiceHealthHeartbeat")
	}
}

// TestFleetSubjects_IncludesBentoLifecycleWithSchema guards the bento subject a watcher frood
// (magpie) declares it emits at register time -- delightd verifyContracts would 422 that emit if
// the subject were not provisioned.
func TestFleetSubjects_IncludesBentoLifecycleWithSchema(t *testing.T) {
	var found bool
	for _, s := range FleetSubjects() {
		if s.Subject == "bento.v1.BentoLifecycleEvent" {
			found = true
			if s.SchemaText == "" {
				t.Error("bento lifecycle subject has empty schema text (the embedded proto did not load)")
			}
		}
	}
	if !found {
		t.Fatal("FleetSubjects must include bento.v1.BentoLifecycleEvent (a watcher declares it emits it)")
	}
}

// provision-schemas registers the fleet's contract SCHEMAS in the Confluent Schema Registry,
// idempotently, from the declared FleetSubjects set. delightd's /register checks a subject exists
// at register time -- before a frood has produced anything -- so the schemas must be provisioned
// explicitly ahead of emit. This is the schema sibling of provision-topics: a tracked artifact run
// every boot, not a hand-run curl that drifts. An already-registered identical schema is success.
//
// The registry URL comes from SCHEMA_REGISTRY_URL. In-cluster that is the Schema Registry Service;
// from the host, point it at a port-forward of the registry's listener.
package main

import (
	"context"
	"log"
	"os"
	"strings"
	"time"

	"github.com/janearc/big-little-mesh/admin"
)

func main() {
	srURL := getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	specs := admin.FleetSubjects()
	if err := admin.EnsureSubjects(ctx, srURL, specs...); err != nil {
		log.Fatalf("provision-schemas: %v", err)
	}

	names := make([]string, len(specs))
	for i, s := range specs {
		names[i] = s.Subject
	}
	log.Printf("provision-schemas: ensured %d subjects on %s: %s",
		len(specs), srURL, strings.Join(names, ", "))
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

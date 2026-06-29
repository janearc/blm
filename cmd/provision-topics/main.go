// provision-topics ensures the fleet's Kafka topics exist, idempotently, from the
// declared FleetTopics set. This is the explicit provisioning path the dry bus needs:
// broker auto-create stays OFF, so topics must be created from a tracked artifact (this
// command) rather than a hand-run `kafka-topics`. Safe to run every boot -- an existing
// topic is success.
//
// Brokers come from KAFKA_BROKERS (comma-separated). In-cluster that is "kafka:9092";
// from the host, point it at the broker's external listener (e.g. via a port-forward of
// kafka 9094).
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
	brokers := strings.Split(getenv("KAFKA_BROKERS", "kafka:9092"), ",")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	specs := admin.FleetTopics()
	if err := admin.EnsureTopics(ctx, brokers, specs...); err != nil {
		log.Fatalf("provision-topics: %v", err)
	}

	names := make([]string, len(specs))
	for i, s := range specs {
		names[i] = s.Name
	}
	log.Printf("provision-topics: ensured %d topics on %s: %s",
		len(specs), strings.Join(brokers, ","), strings.Join(names, ", "))
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

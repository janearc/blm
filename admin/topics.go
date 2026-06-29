// Package admin is frood's Kafka administration surface: the operations
// the bus owner (kafka-svc) needs on top of plain emit/consume. This is the
// "superset" -- a simple frood produces and consumes; kafka-svc also provisions
// the topics the fleet agreed on. Codifying it here means topic creation is
// idempotent library code that kafka-svc calls, not a hand-run `kafka-topics`
// command that drifts.
package admin

import (
	"context"
	"errors"
	"fmt"

	"github.com/twmb/franz-go/pkg/kadm"
	"github.com/twmb/franz-go/pkg/kerr"
	"github.com/twmb/franz-go/pkg/kgo"
)

// TopicSpec declares one topic's desired shape. Configs are raw Kafka topic
// configs (e.g. "retention.ms"); a nil value means "broker default".
type TopicSpec struct {
	Name              string
	Partitions        int32
	ReplicationFactor int16
	Configs           map[string]*string
}

// EnsureTopics creates each spec's topic if it does not already exist. It is
// idempotent: a topic that is already present is treated as success, so the
// caller can run this unconditionally at startup. Auto-create stays OFF on the
// broker; this is the explicit, declared provisioning path.
//
// It opens (and closes) its own short-lived client from brokers, so a provisioner
// does not need to share a producer/consumer client.
func EnsureTopics(ctx context.Context, brokers []string, specs ...TopicSpec) error {
	if len(brokers) == 0 {
		return fmt.Errorf("no kafka brokers configured")
	}
	cl, err := kgo.NewClient(kgo.SeedBrokers(brokers...))
	if err != nil {
		return err
	}
	defer cl.Close()
	if err := cl.Ping(ctx); err != nil {
		return fmt.Errorf("kafka unreachable: %w", err)
	}

	adm := kadm.NewClient(cl)
	for _, s := range specs {
		// CreateTopics takes one partition/replication per call, so provision
		// per-spec to allow each topic its own shape and configs.
		resp, err := adm.CreateTopics(ctx, s.Partitions, s.ReplicationFactor, s.Configs, s.Name)
		if err != nil {
			return fmt.Errorf("create topic %q: %w", s.Name, err)
		}
		for _, r := range resp {
			// An already-existing topic is the idempotent success case, not an
			// error -- this is exactly what lets the provisioner run every boot.
			if r.Err != nil && !errors.Is(r.Err, kerr.TopicAlreadyExists) {
				return fmt.Errorf("create topic %q: %w", r.Topic, r.Err)
			}
		}
	}
	return nil
}

// FleetTopics is the v0.5 topic set, declared once so it is provisioned exactly as
// the contracts assume. Single broker on the laptop -> replication 1, one partition;
// revisit per-topic when the mesh grows. Code is truth on the names (verified against
// the producers/consumers):
//   - observability.events -- service heartbeats (ServiceHealthHeartbeat). TokenBurnEvent
//     rides this topic too via RecordNameStrategy, so there is no separate token-burn topic.
//   - bento.events          -- the bento lifecycle (dummy + the per-pipeline sidecars)
//   - delight.events        -- delightd backup/domain events (BackupEvent)
//   - paling.events         -- paling's BanchanLifecycleEvent
//   - magpie.events         -- magpie's events (declared ahead of magpie landing)
func FleetTopics() []TopicSpec {
	const (
		parts = int32(1)
		repl  = int16(1)
	)
	return []TopicSpec{
		{Name: "observability.events", Partitions: parts, ReplicationFactor: repl},
		{Name: "bento.events", Partitions: parts, ReplicationFactor: repl},
		{Name: "delight.events", Partitions: parts, ReplicationFactor: repl},
		{Name: "paling.events", Partitions: parts, ReplicationFactor: repl},
		{Name: "magpie.events", Partitions: parts, ReplicationFactor: repl},
	}
}

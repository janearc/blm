// Command sidecar is the frood emit sidecar: the container companion to a
// bare-metal Python pipeline (which needs Metal/MLX and so lives off the docker
// network). The pipeline POSTs bento lifecycle events here; the sidecar owns the
// protobuf + Schema-Registry + Kafka wire, so Python never touches Kafka. Modeled on
// paling's working sidecar, scoped to bento.v1 and the shared bento.events topic.
//
// Best-effort by design: if Kafka/SR is unreachable the publisher is nil and /emit
// accepts-and-drops, so a bus hiccup never blocks the pipeline. The durable record is
// the bus; a missed emit is recovered by re-handling the work, never by failing it.
package main

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/janearc/big-little-mesh/emit"
	bentov1 "github.com/janearc/big-little-mesh/gen/go/bento/v1"
	observabilityv1 "github.com/janearc/big-little-mesh/gen/go/observability/v1"
	bentoproto "github.com/janearc/big-little-mesh/proto/bento/v1"
	observabilityproto "github.com/janearc/big-little-mesh/proto/observability/v1"
)

const (
	// the shared bento lifecycle topic; consumers filter by bento_kind. delightd does
	// NOT subscribe here (it is the registry/orchestrator, not a bento consumer).
	topicBentoEvents = "bento.events"
	subjectBento     = "bento.v1.BentoLifecycleEvent"

	// the observability topic obs-svc consumes; the sidecar is the frood's only
	// producer, so the heartbeat is the one thing touching kafka on its behalf.
	topicObservability = "observability.events"
	subjectHeartbeat   = "observability.v1.ServiceHealthHeartbeat"
)

var startTime = time.Now()

var log = slog.New(slog.NewJSONHandler(os.Stderr, nil))

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

// emitIntake decodes a BentoLifecycleEvent (protojson -- the contract's canonical JSON,
// not a hand-mapped subset) and publishes it to bento.events. A nil publisher accepts
// and drops, so the sidecar runs and stays useful before the bus is up.
func emitIntake(ctx context.Context, pub *emit.Publisher) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "read failed", http.StatusBadRequest)
			return
		}
		ev := &bentov1.BentoLifecycleEvent{}
		if err := protojson.Unmarshal(body, ev); err != nil {
			http.Error(w, "bad protojson", http.StatusBadRequest)
			return
		}
		// a nil publisher (dry bus) returns nil here -- accept-and-drop, best-effort.
		if err := pub.Publish(ctx, topicBentoEvents, subjectBento, bentoproto.Schema, ev.GetBentoId(), ev); err != nil {
			log.Error("bento lifecycle emit failed", "err", err, "bento_id", ev.GetBentoId())
			http.Error(w, "emit failed", http.StatusBadGateway)
			return
		}
		w.WriteHeader(http.StatusAccepted)
	}
}

// startHeartbeat polls the pipeline's /health and emits a ServiceHealthHeartbeat on a
// ticker. Best-effort: a poll or publish failure is logged, never fatal. The heartbeat
// is the observability signal obs-svc consumes -- the frood pipeline never emits it
// itself; the sidecar does, reflecting the poll (GREEN when /health is ok, else RED).
func startHeartbeat(ctx context.Context, pub *emit.Publisher, serviceName, healthURL string) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	client := &http.Client{Timeout: 3 * time.Second}
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			state := observabilityv1.HealthState_HEALTH_STATE_RED
			if resp, err := client.Get(healthURL); err == nil {
				if resp.StatusCode == http.StatusOK {
					state = observabilityv1.HealthState_HEALTH_STATE_GREEN
				}
				_ = resp.Body.Close()
			}
			hb := &observabilityv1.ServiceHealthHeartbeat{
				ServiceName:    serviceName,
				CurrentState:   state,
				UptimeSeconds:  uint32(time.Since(startTime).Seconds()),
				Timestamp:      timestamppb.Now(),
				IdempotencyKey: fmt.Sprintf("%s-hb-%d", serviceName, time.Now().UnixNano()),
			}
			if err := pub.Publish(ctx, topicObservability, subjectHeartbeat, observabilityproto.Schema, hb.GetServiceName(), hb); err != nil {
				log.Error("heartbeat emit failed", "err", err)
			}
		}
	}
}

func main() {
	log.Info("starting frood emit sidecar")

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// best-effort: a dry/unreachable bus disables emission but never stops the sidecar.
	// the connect is bounded so a dead bus can't hang startup -- emission stays off
	// until restarted into a live bus.
	var publisher *emit.Publisher
	brokers := strings.Split(getenv("KAFKA_BROKERS", "kafka:9092"), ",")
	pingCtx, pingCancel := context.WithTimeout(ctx, 5*time.Second)
	defer pingCancel()
	if pub, err := emit.New(pingCtx, brokers, getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")); err != nil {
		log.Warn("kafka emission disabled (best-effort); /emit will accept-and-drop", "err", err)
	} else {
		publisher = pub
		defer publisher.Close()
		log.Info("kafka emission ready", "topic", topicBentoEvents)
		// the heartbeat needs a real identity. SERVICE_NAME has NO default on purpose:
		// this sidecar is shared by every python pipeline, so a default would make them
		// all heartbeat as one service on the bus. Each deployment sets it to its
		// pipeline's name (magpie, paling, ...); unset -> no heartbeat, never a fake one.
		serviceName := os.Getenv("SERVICE_NAME")
		if serviceName == "" {
			log.Warn("SERVICE_NAME unset; heartbeat disabled (set it to this pipeline's name)")
		} else {
			// healthURL is the pipeline's bare-metal /health that the sidecar polls each
			// tick. Port 8090 is the fleet convention for a pipeline daemon's health
			// endpoint (paling serve listens there; magpie on 8092) -- set
			// PIPELINE_HEALTH_URL per pipeline. host.docker.internal is the
			// container->host gateway, because the pipeline runs bare-metal (Metal/MLX),
			// off the docker network.
			healthURL := getenv("PIPELINE_HEALTH_URL", "http://host.docker.internal:8090/health")
			go startHeartbeat(ctx, publisher, serviceName, healthURL)
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/emit", emitIntake(ctx, publisher))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"frood-sidecar"}`))
	})

	server := &http.Server{Addr: getenv("SIDECAR_ADDR", ":9090"), Handler: mux}
	go func() {
		log.Info("listening", "addr", server.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("server error", "err", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Info("shutting down sidecar")
	shutCtx, shutCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutCancel()
	if err := server.Shutdown(shutCtx); err != nil {
		log.Error("server shutdown failed", "err", err)
		os.Exit(1)
	}
	log.Info("sidecar exited cleanly")
}

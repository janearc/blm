// Command sidecar is the good-citizen emit sidecar: the container companion to a
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
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"google.golang.org/protobuf/encoding/protojson"

	"github.com/janearc/blm/emit"
	bentov1 "github.com/janearc/blm/gen/go/bento/v1"
	bentoproto "github.com/janearc/blm/proto/bento/v1"
)

const (
	// the shared bento lifecycle topic; consumers filter by bento_kind. delightd does
	// NOT subscribe here (it is the registry/orchestrator, not a bento consumer).
	topicBentoEvents = "bento.events"
	subjectBento     = "bento.v1.BentoLifecycleEvent"
)

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

func main() {
	log.Info("starting good-citizen emit sidecar")

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
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/emit", emitIntake(ctx, publisher))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"good-citizen-sidecar"}`))
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

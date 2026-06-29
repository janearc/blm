// Command dummy is frood's reference service and its release gate: a new
// frood release is proven against the dummy, never against a production service
// (delightd, paling, ...). It has its own service id so its heartbeats and events are
// distinguishable on the bus.
//
// dummy is the executable spec every frood is modeled on. It does the full frood
// loop: emit a heartbeat, watch an inbox, and -- for each new input -- drive a
// SYNTHETIC bento through the generated bento FSM, emitting a BentoLifecycleEvent on
// every transition (NOTICED -> COOK -> DONE). The work is synthetic (the handlers just
// transition); what is real is the FSM dispatch and the emit, which is exactly what a
// release must prove. Kafka is best-effort -- with no broker reachable it drives the
// FSM and logs, with emission off.
package main

import (
	"context"
	"crypto/rand"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/janearc/big-little-mesh/emit"
	"github.com/janearc/big-little-mesh/frood"
	bentov1 "github.com/janearc/big-little-mesh/gen/go/bento/v1"
	bentoproto "github.com/janearc/big-little-mesh/proto/bento/v1"
	observabilityproto "github.com/janearc/big-little-mesh/proto/observability/v1"
	"github.com/janearc/big-little-mesh/watcher"
)

const (
	// serviceID is the dummy's identity on the bus -- deliberately not a real service
	// name, so its telemetry never masquerades as a production frood's.
	serviceID = "frood-dummy"

	topicBentoEvents = "bento.events"
	subjectBento     = "bento.v1.BentoLifecycleEvent"
	bentoKind        = "dummy"
)

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// newID returns a uuid4 -- the lifecycle event's idempotency key.
func newID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// handlers binds synthetic behavior to the bento FSM: each state transitions to the
// next, which is enough to drive a bento through the lifecycle and exercise the
// generated dispatch + emit. A real frood does work here; the dummy proves the path.
type handlers struct{ log *slog.Logger }

func (h handlers) OnNoticed(_ context.Context, b *bentov1.Bento) (bentov1.BentoState, error) {
	h.log.Info("dummy: noticed", "bento", b.GetId())
	return bentov1.BentoState_BENTO_STATE_COOK, nil
}

func (h handlers) OnCook(_ context.Context, b *bentov1.Bento) (bentov1.BentoState, error) {
	h.log.Info("dummy: cooking", "bento", b.GetId())
	return bentov1.BentoState_BENTO_STATE_DONE, nil
}

func (h handlers) OnPartial(_ context.Context, b *bentov1.Bento) (bentov1.BentoState, error) {
	return bentov1.BentoState_BENTO_STATE_DONE, nil
}

func (h handlers) OnDone(_ context.Context, b *bentov1.Bento) (bentov1.BentoState, error) {
	h.log.Info("dummy: done", "bento", b.GetId())
	return bentov1.BentoState_BENTO_STATE_UNSPECIFIED, nil // terminal
}

func (h handlers) OnFailed(_ context.Context, b *bentov1.Bento) (bentov1.BentoState, error) {
	h.log.Error("dummy: failed", "bento", b.GetId())
	return bentov1.BentoState_BENTO_STATE_UNSPECIFIED, nil // terminal
}

// busEmitter publishes a BentoLifecycleEvent on each transition. A nil publisher is a
// no-op (best-effort), so the FSM still drives with the bus down.
type busEmitter struct {
	pub *emit.Publisher
	log *slog.Logger
}

func (e busEmitter) EmitLifecycle(ctx context.Context, b *bentov1.Bento, st bentov1.BentoState) error {
	ev := &bentov1.BentoLifecycleEvent{
		EventId:   newID(),
		TraceId:   b.GetId(),
		BentoId:   b.GetId(),
		BentoKind: b.GetKind(),
		State:     st,
		Handler:   serviceID,
	}
	e.log.Info("dummy: emit", "bento", b.GetId(), "state", st)
	return e.pub.Publish(ctx, topicBentoEvents, subjectBento, bentoproto.Schema, b.GetId(), ev)
}

// drive walks one synthetic bento from NOTICED through the FSM until a handler returns
// the terminal state, one Step at a time -- proving the generated dispatch + emit.
func drive(ctx context.Context, h handlers, e busEmitter, log *slog.Logger, name string) {
	b := &bentov1.Bento{Id: newID(), Name: name, Kind: bentoKind, State: bentov1.BentoState_BENTO_STATE_NOTICED}
	log.Info("dummy: driving synthetic bento", "bento", b.GetId(), "trigger", name)
	for {
		prev := b.GetState()
		if err := bentov1.Step(ctx, h, e, b); err != nil {
			log.Error("dummy: step failed", "bento", b.GetId(), "err", err)
			return
		}
		if b.GetState() == prev { // terminal: handler returned UNSPECIFIED
			break
		}
	}
	log.Info("dummy: synthetic bento finished", "bento", b.GetId(), "final", b.GetState())
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stderr, nil))

	inbox := getenv("DUMMY_INBOX", "/tmp/frood-dummy/inbox")
	brokers := strings.Split(getenv("KAFKA_BROKERS", "kafka:9092"), ",")
	srURL := getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// emission is best-effort: a down broker disables it but never stops the service.
	var pub *emit.Publisher
	if p, err := emit.New(ctx, brokers, srURL); err != nil {
		log.Warn("kafka emission disabled", "err", err)
	} else {
		pub = p
		defer pub.Close()
		log.Info("kafka emission ready")
		go frood.Heartbeat(ctx, pub, serviceID, observabilityproto.Schema, 15*time.Second, log)
	}

	h := handlers{log: log}
	e := busEmitter{pub: pub, log: log}

	// watch the inbox; each new input drives a synthetic bento through the FSM.
	w := watcher.New(watcher.NewFilesOracle(inbox), 5*time.Second, func(ctx context.Context, r watcher.Result) error {
		for _, item := range r.Items {
			drive(ctx, h, e, log, item)
		}
		return nil
	}, log)
	go w.Run(ctx)

	log.Info("frood dummy running", "service", serviceID, "inbox", inbox)
	<-ctx.Done()
	log.Info("frood dummy stopped")
}

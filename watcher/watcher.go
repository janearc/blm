// Package watcher is the frood watch loop: a generic poll loop driven by
// a pluggable Oracle. It is the generalization of delightd's git oracle -- in
// delightd, the only git-specific part was "is the working tree dirty?"; the
// per-target goroutine + ticker + react-on-change machinery was already generic.
// Here that machinery lives once, and the "is there work?" question is an Oracle
// implementation: git churn, new files in a directory, or anything else.
//
// The heavy go-git dependency lives in the watcher/git subpackage so a consumer
// that only watches a directory (e.g. magpie) does not pull it in. This core
// package is standard-library only.
package watcher

import (
	"context"
	"log/slog"
	"time"
)

// Result is what an Oracle reports for one poll. HasWork is the trigger; Items
// carries the concrete work when the Oracle can name it (e.g. new file paths).
// A git-churn Oracle sets HasWork without Items; a new-files Oracle fills both.
type Result struct {
	HasWork bool
	Items   []string
}

// Oracle answers "is there work to do?" for some target. Implementations:
// watcher/git.ChurnOracle (dirty working tree) and watcher.FilesOracle (new
// files in a directory). Keep implementations cheap -- they run every tick.
type Oracle interface {
	// Name identifies the oracle in logs and metrics.
	Name() string
	// Poll reports whether there is work right now. An error is logged by the
	// loop and treated as "no work this tick" -- a flaky oracle must not wedge
	// the loop, the same best-effort stance the rest of frood takes.
	Poll(ctx context.Context) (Result, error)
}

// Handler reacts to a positive poll. For an event-driven frood this is
// typically "emit a Kafka event describing the work"; the service that watches
// is the service that acts. A handler error is logged and the loop continues.
type Handler func(ctx context.Context, r Result) error

// Watcher pairs one Oracle with one Handler on a fixed interval. One Watcher
// watches one target; run several for several targets (as delightd runs one per
// project).
type Watcher struct {
	oracle   Oracle
	interval time.Duration
	handler  Handler
	log      *slog.Logger
}

// New builds a Watcher. interval is the poll cadence; a non-positive interval
// defaults to 15s (delightd's default check cadence). A nil logger is replaced
// with the default so callers never have to supply one.
func New(oracle Oracle, interval time.Duration, handler Handler, log *slog.Logger) *Watcher {
	if interval <= 0 {
		interval = 15 * time.Second
	}
	if log == nil {
		log = slog.Default()
	}
	return &Watcher{oracle: oracle, interval: interval, handler: handler, log: log}
}

// Run polls until ctx is cancelled. It blocks, so callers run it in a goroutine
// (one per target). Oracle and handler errors are logged, never fatal: a watch
// loop that dies on a transient error is worse than one that retries next tick.
func (w *Watcher) Run(ctx context.Context) {
	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			res, err := w.oracle.Poll(ctx)
			if err != nil {
				w.log.Error("oracle poll failed", "oracle", w.oracle.Name(), "err", err)
				continue
			}
			if !res.HasWork {
				continue
			}
			if err := w.handler(ctx, res); err != nil {
				w.log.Error("watch handler failed", "oracle", w.oracle.Name(), "items", len(res.Items), "err", err)
			}
		}
	}
}

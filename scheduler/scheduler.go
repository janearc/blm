// Package scheduler is frood's "alarms, not polling" primitive: a thin
// wrapper over go-quartz so a frood schedules recurring work without hand-
// rolling timers. This is the Cadence lesson applied -- we built our own
// scheduler once and it was a maintenance burden; here we wrap an existing
// library and expose just the two shapes froods actually need (fixed interval
// and cron). Durable multi-step workflow orchestration (Temporal) is a separate,
// later concern, deliberately not in scope.
package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/reugn/go-quartz/job"
	"github.com/reugn/go-quartz/quartz"
)

// Scheduler runs named recurring jobs. Construct one, Start it with a context,
// register jobs with Every/Cron, and Stop it on shutdown.
type Scheduler struct {
	sched quartz.Scheduler
	log   *slog.Logger
}

// New builds a Scheduler. A nil logger defaults to slog.Default.
func New(log *slog.Logger) (*Scheduler, error) {
	if log == nil {
		log = slog.Default()
	}
	sched, err := quartz.NewStdScheduler()
	if err != nil {
		return nil, err
	}
	return &Scheduler{sched: sched, log: log}, nil
}

// Start begins executing scheduled jobs; it returns immediately. Jobs run until
// Stop or until ctx is cancelled.
func (s *Scheduler) Start(ctx context.Context) { s.sched.Start(ctx) }

// Stop halts the scheduler and waits for the worker to exit.
func (s *Scheduler) Stop() { s.sched.Stop() }

// Every schedules fn to run on a fixed interval under a unique name. The name
// identifies the job in logs and must be unique within this scheduler.
func (s *Scheduler) Every(name string, interval time.Duration, fn func(context.Context) error) error {
	return s.schedule(name, quartz.NewSimpleTrigger(interval), fn)
}

// Cron schedules fn on a cron expression (go-quartz cron syntax, e.g.
// "0 0 * * * *" for the top of every hour).
func (s *Scheduler) Cron(name, expr string, fn func(context.Context) error) error {
	trig, err := quartz.NewCronTrigger(expr)
	if err != nil {
		return fmt.Errorf("bad cron expression %q: %w", expr, err)
	}
	return s.schedule(name, trig, fn)
}

// schedule wraps fn as a go-quartz job and registers it under trig. The wrapper
// logs a job error so a failing tick is visible but never wedges the scheduler --
// the same best-effort stance the rest of frood takes.
func (s *Scheduler) schedule(name string, trig quartz.Trigger, fn func(context.Context) error) error {
	fjob := job.NewFunctionJob(func(ctx context.Context) (any, error) {
		if err := fn(ctx); err != nil {
			s.log.Error("scheduled job failed", "job", name, "err", err)
			return nil, err
		}
		return nil, nil
	})
	detail := quartz.NewJobDetail(fjob, quartz.NewJobKey(name))
	return s.sched.ScheduleJob(detail, trig)
}

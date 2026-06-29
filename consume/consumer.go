// Package consume is frood's inbound Kafka boundary, the mirror of emit.
// It polls a topic in a consumer group, strips the Confluent Schema-Registry
// protobuf wire framing, and hands the raw payload to a Handler that unmarshals
// it into the caller's own message type -- frood owns the wire format,
// the caller owns the domain type.
//
// Availability mirrors emit: a down broker is logged and retried with backoff,
// never fatal; New returns an error the caller logs-and-proceeds on; a nil
// *Consumer is a valid no-op so a service can hold one unconditionally.
package consume

import (
	"context"
	"encoding/binary"
	"fmt"
	"log/slog"
	"time"

	"github.com/cenkalti/backoff/v4"
	"github.com/twmb/franz-go/pkg/kgo"
)

// Handler processes one record's protobuf payload, with the Confluent SR framing
// already stripped. The caller unmarshals payload into its own proto type. A
// handler error is logged and the record still advances -- the system of record
// is downstream, and producers re-issue idempotent messages rather than rely on
// Kafka redelivery to a process that may be mid-restart.
type Handler func(ctx context.Context, payload []byte, rec *kgo.Record) error

// Consumer reads from one topic in one consumer group.
type Consumer struct {
	client *kgo.Client
	log    *slog.Logger
}

// New connects the consumer at the latest offset (live traffic, not a backlog to
// replay). An error means inbound consumption is unavailable; log it and proceed
// with a nil Consumer. A nil logger defaults to slog.Default.
func New(ctx context.Context, brokers []string, topic, group string, log *slog.Logger) (*Consumer, error) {
	if len(brokers) == 0 {
		return nil, fmt.Errorf("no kafka brokers configured")
	}
	if log == nil {
		log = slog.Default()
	}
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ConsumerGroup(group),
		kgo.ConsumeTopics(topic),
		kgo.ConsumeResetOffset(kgo.NewOffset().AtEnd()),
	)
	if err != nil {
		return nil, err
	}
	if err := cl.Ping(ctx); err != nil {
		cl.Close()
		return nil, fmt.Errorf("kafka unreachable: %w", err)
	}
	return &Consumer{client: cl, log: log}, nil
}

// Close releases the consumer.
func (c *Consumer) Close() {
	if c != nil && c.client != nil {
		c.client.Close()
	}
}

// Run drives the poll loop until ctx is cancelled. A nil Consumer returns
// immediately. Poll errors retry with exponential backoff + jitter so a
// transient broker outage degrades into retry rather than a crash. A record
// whose framing cannot be stripped is logged and dropped (malformed is not
// retryable); the loop keeps moving.
func (c *Consumer) Run(ctx context.Context, h Handler) {
	if c == nil {
		return
	}
	b := backoff.NewExponentialBackOff()
	b.InitialInterval = 100 * time.Millisecond
	b.MaxInterval = 30 * time.Second
	b.MaxElapsedTime = 0 // never give up; live as long as the service does
	b.RandomizationFactor = 0.1

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		fetches := c.client.PollFetches(ctx)
		if errs := fetches.Errors(); len(errs) > 0 {
			if ctx.Err() != nil {
				return
			}
			for _, e := range errs {
				c.log.Error("consume poll error", "topic", e.Topic, "err", e.Err)
			}
			select {
			case <-ctx.Done():
				return
			case <-time.After(b.NextBackOff()):
			}
			continue
		}
		b.Reset()
		fetches.EachRecord(func(rec *kgo.Record) {
			payload, err := StripFrame(rec.Value)
			if err != nil {
				c.log.Error("consume decode failed (dropping)", "topic", rec.Topic, "err", err)
				return
			}
			if err := h(ctx, payload, rec); err != nil {
				c.log.Error("consume handler failed", "topic", rec.Topic, "err", err)
			}
		})
	}
}

// StripFrame removes the Confluent Schema-Registry protobuf wire framing and
// returns the protobuf payload. It is the exact inverse of emit.encode:
//
//	byte 0    : magic 0x00
//	bytes 1-4 : schema id, big-endian (ignored on read -- the type is fixed by
//	            the topic/handler, not carried per-message)
//	N bytes   : message-index (single 0x00 for a first/only message, else a
//	            zig-zag varint count followed by that many zig-zag varint indices)
//	rest      : serialized protobuf payload
//
// The general varint message-index path is handled even though most messages use
// the 0x00 optimization, so a multi-message schema file does not silently corrupt
// decoding -- the same sharp edge emit.encode guards on the write side.
func StripFrame(frame []byte) ([]byte, error) {
	if len(frame) < 5 || frame[0] != 0x00 {
		return nil, fmt.Errorf("not a confluent SR frame (len=%d)", len(frame))
	}
	rest := frame[5:] // skip magic + 4-byte schema id
	if len(rest) == 0 {
		return nil, fmt.Errorf("frame truncated before message-index")
	}
	if rest[0] == 0x00 {
		return rest[1:], nil
	}
	count, n := binary.Varint(rest)
	if n <= 0 {
		return nil, fmt.Errorf("bad message-index count varint")
	}
	rest = rest[n:]
	for i := int64(0); i < count; i++ {
		_, n := binary.Varint(rest)
		if n <= 0 {
			return nil, fmt.Errorf("bad message-index varint")
		}
		rest = rest[n:]
	}
	return rest, nil
}

// HAND-WRITTEN golden conformance test for the big-little-mesh-contracts protojson wire. This
// file is NOT generated -- it lives in tests/ (the crate's hand-written integration-test home,
// which `buf generate` never writes to, so it is drift-safe alongside the generated src/) and is
// the human-authored ground truth the generated #[cfg(test)] conformance module cannot be.
//
// Why it must be hand-written: the generated protojson_tests in src/observability/v1.rs are
// emitted by the SAME plugin that emits the structs. A plugin bug -- a wrong #[serde(rename)], a
// dropped skip_serializing_if, a mis-cased enum value -- would corrupt the struct AND emit an
// assertion that agrees with the corruption, so the generated test passes while the wire is
// wrong. This test pins the wire against LITERAL json strings a human wrote from the protojson
// spec, so a plugin regression that the self-referential tests would wave through fails HERE.
//
// The bytes below are canonical protojson: lowerCamelCase keys, enum values as their full
// SCREAMING_SNAKE proto names, fields in proto declaration order, and unset Option fields omitted.
//
// This is a SNAPSHOT of the current wire surface, not an automatic guard: adding a NEW message,
// or a new OPTIONAL field on a covered message, is silently uncovered here (a None field
// round-trips byte-identically, so an existing test stays green). When observability.proto grows
// a message or an optional field, add a golden case for it. (Adding a required field is already
// loud -- it breaks the struct literals and the byte-exact round-trips below.)

use big_little_mesh_contracts::observability::v1::{
    FleetMetrics, HealthState, QuotaMetrics, ServiceHealthHeartbeat, TokenBurnEvent,
    WidgetStatePayload,
};

#[test]
fn health_state_wire_names_are_pinned() {
    // Each enum variant's exact protojson spelling, pinned by hand. If the plugin renames a
    // variant, this fails even though the generated test (which reads back its own output) would not.
    let pairs = [
        (HealthState::HealthStateUnspecified, "\"HEALTH_STATE_UNSPECIFIED\""),
        (HealthState::HealthStateGreen, "\"HEALTH_STATE_GREEN\""),
        (HealthState::HealthStateYellow, "\"HEALTH_STATE_YELLOW\""),
        (HealthState::HealthStateRed, "\"HEALTH_STATE_RED\""),
        (HealthState::HealthStateExhausted, "\"HEALTH_STATE_EXHAUSTED\""),
    ];
    for (variant, wire) in pairs {
        assert_eq!(serde_json::to_string(&variant).unwrap(), wire, "encode {variant:?}");
        assert_eq!(
            serde_json::from_str::<HealthState>(wire).unwrap(),
            variant,
            "decode {wire}"
        );
    }
    // An unrecognized value decodes to Unknown rather than failing the parse (forward-compat).
    assert_eq!(
        serde_json::from_str::<HealthState>("\"HEALTH_STATE_SOMETHING_NEW\"").unwrap(),
        HealthState::Unknown
    );
}

#[test]
fn service_health_heartbeat_round_trips_canonical_bytes() {
    // A fully-populated heartbeat, written by hand in canonical protojson (keys in struct order,
    // present timestamp, non-default enum). Decode it and assert every field value...
    let canonical = concat!(
        r#"{"serviceName":"magpie","currentState":"HEALTH_STATE_GREEN","uptimeSeconds":3600,"#,
        r#""internalLoadMetric":42,"timestamp":"2026-06-30T12:00:00Z","idempotencyKey":"hb-abc-123"}"#
    );
    let hb: ServiceHealthHeartbeat = serde_json::from_str(canonical).unwrap();
    assert_eq!(hb.service_name, "magpie");
    assert_eq!(hb.current_state, HealthState::HealthStateGreen);
    assert_eq!(hb.uptime_seconds, 3600);
    assert_eq!(hb.internal_load_metric, 42);
    assert_eq!(hb.timestamp.as_deref(), Some("2026-06-30T12:00:00Z"));
    assert_eq!(hb.idempotency_key, "hb-abc-123");
    // ...then re-encode and assert it is byte-identical to the canonical wire (pins key names,
    // field order, and the camelCase rename all at once).
    assert_eq!(serde_json::to_string(&hb).unwrap(), canonical);
}

#[test]
fn heartbeat_omits_unset_timestamp() {
    // A heartbeat with no timestamp omits the key entirely (skip_serializing_if), it does not emit
    // null -- so a consumer can tell "no timestamp" from "timestamp present". A default struct's
    // other fields still emit (proto3 zero values are on the wire); only the Option is omitted.
    let hb = ServiceHealthHeartbeat {
        service_name: "paling".to_string(),
        current_state: HealthState::HealthStateUnspecified,
        uptime_seconds: 0,
        internal_load_metric: 0,
        timestamp: None,
        idempotency_key: "hb-1".to_string(),
    };
    let wire = serde_json::to_string(&hb).unwrap();
    assert!(!wire.contains("timestamp"), "unset timestamp must be omitted: {wire}");
    assert_eq!(
        wire,
        concat!(
            r#"{"serviceName":"paling","currentState":"HEALTH_STATE_UNSPECIFIED","#,
            r#""uptimeSeconds":0,"internalLoadMetric":0,"idempotencyKey":"hb-1"}"#
        )
    );
}

#[test]
fn token_burn_event_optional_fields_omitted_when_absent() {
    // TokenBurnEvent has two Option fields (cost_estimated_micro_usd, timestamp); both are omitted
    // when None. A literal wire with only the required fields decodes them to None.
    let canonical =
        r#"{"agentId":"echo","actionContext":"summarize","tokensConsumed":1500,"idempotencyKey":"tb-9"}"#;
    let ev: TokenBurnEvent = serde_json::from_str(canonical).unwrap();
    assert_eq!(ev.agent_id, "echo");
    assert_eq!(ev.action_context, "summarize");
    assert_eq!(ev.tokens_consumed, 1500);
    assert_eq!(ev.cost_estimated_micro_usd, None);
    assert_eq!(ev.timestamp, None);
    assert_eq!(ev.idempotency_key, "tb-9");
    assert_eq!(serde_json::to_string(&ev).unwrap(), canonical);
}

#[test]
fn widget_state_payload_nests_and_omits() {
    // The empty payload is "{}" -- every field is an Option omitted when None, so a widget with
    // nothing yet is an empty object, not a wall of nulls.
    assert_eq!(serde_json::to_string(&WidgetStatePayload::default()).unwrap(), "{}");

    // A populated payload nests FleetMetrics and QuotaMetrics under their camelCase keys, with the
    // health enums as their proto names. Pinned by hand, byte-for-byte.
    let canonical = concat!(
        r#"{"calculatedAt":"2026-06-30T12:00:00Z","#,
        r#""fleet":{"overallHealth":"HEALTH_STATE_YELLOW","activeNodes":3,"degradedNodes":1,"#,
        r#""activeDiscoveryEndpoint":"obs-svc-agg.fleet:8090"},"#,
        r#""quota":{"runwayState":"HEALTH_STATE_GREEN","runwayMinutesRemaining":120,"#,
        r#""burnRateTokensPerMinute":250,"absoluteQuotaRemainingCents":4200}}"#
    );
    let payload = WidgetStatePayload {
        calculated_at: Some("2026-06-30T12:00:00Z".to_string()),
        fleet: Some(FleetMetrics {
            overall_health: HealthState::HealthStateYellow,
            active_nodes: 3,
            degraded_nodes: 1,
            active_discovery_endpoint: "obs-svc-agg.fleet:8090".to_string(),
        }),
        quota: Some(QuotaMetrics {
            runway_state: HealthState::HealthStateGreen,
            runway_minutes_remaining: 120,
            burn_rate_tokens_per_minute: 250,
            absolute_quota_remaining_cents: 4200,
        }),
    };
    assert_eq!(serde_json::to_string(&payload).unwrap(), canonical);
    let decoded: WidgetStatePayload = serde_json::from_str(canonical).unwrap();
    assert_eq!(decoded, payload);
}

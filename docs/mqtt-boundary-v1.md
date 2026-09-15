# MQTT message boundary v1.0

## Topic

The only accepted shape is:

```text
edge-evidence/v1/<source_id>/<event_type>
```

`source_id` and `event_type` come only from the topic. They are deliberately
absent from the payload so a delivery cannot present two competing authorities.
Both values must pass the canonical event identifier contract.

## Payload

The MQTT payload is UTF-8 JSON with exactly these fields:

| Field | Meaning |
|---|---|
| `event_id` | Stable idempotency identity |
| `source_sequence` | Non-negative sequence assigned at the source |
| `observed_at` | Explicit UTC observation time |
| `payload` | Domain-neutral observation object |
| `metadata` | Domain-neutral provenance object |

Unknown and missing fields fail closed. `schema_version=1.0` is selected by the
`v1` topic segment. `ingested_at` is the explicit UTC receipt time supplied by
the receiving callback, never copied from producer-controlled JSON.

## Delivery semantics

The adapter assumes at-least-once delivery may redeliver a message. For a known
`event_id`, it compares topic and producer-controlled fields with the committed
event while retaining the original receipt time. A matching retry is classified
as a duplicate even if it arrives later; conflicting reuse fails closed.

Runtime counters expose received, accepted, duplicate and rejected messages as
well as disconnect and reconnect notifications. They are process-local
observations, not a metrics-storage system.

## Integration boundary

`MqttIngestionRuntime.ingest(topic, payload, received_at=...)` is a
broker-client-neutral callback target. A concrete client can pass raw topic and
payload bytes into it. M6 does not embed credentials, select a broker library or
claim interoperability certification with a specific broker product.

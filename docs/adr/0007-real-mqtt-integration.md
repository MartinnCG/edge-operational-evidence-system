# ADR-0007: Real MQTT integration with manual acknowledgement

- Status: Accepted
- Milestone: M7

## Context

M6 validates topic and payload semantics but does not open a network connection
to a broker. A real integration must avoid acknowledging QoS 1 delivery before
the message has been classified and, for accepted input, durably committed.

## Decision

Use the optional Paho MQTT 2.x client with callback API v2, MQTT 3.1.1,
`clean_session=False`, automatic reconnect and manual acknowledgement. Subscribe
at QoS 1. Invoke the broker-neutral runtime first and acknowledge only after it
returns a durable acceptance, an idempotent duplicate or a bounded rejection.
Unexpected processing exceptions remain unacknowledged.

Run integration tests against the pinned official
`eclipse-mosquitto:2.1.2-alpine` image. Bind its unauthenticated test listener to
host loopback only and use synthetic events. Stop and start the container during
the test while preserving its named data volume.

## Consequences

- Broker I/O is isolated from event, ledger and replay semantics.
- The real-broker test covers retained QoS 1 delivery and reconnect behavior.
- Unit tests inject a fake Paho module and require neither network nor Docker.
- Authentication, TLS, broker clustering and physical network failure remain
  explicit future work.

## References

- [Eclipse Paho Python client API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
- [Official Eclipse Mosquitto container image](https://hub.docker.com/_/eclipse-mosquitto)

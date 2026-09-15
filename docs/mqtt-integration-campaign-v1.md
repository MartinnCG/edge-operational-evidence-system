# Real MQTT integration campaign v1.0

## Reproducible environment

- Eclipse Mosquitto `2.1.2-alpine`, pinned in Docker Compose.
- Paho MQTT Python `>=2.1,<3`, installed through the `mqtt` package extra.
- MQTT 3.1.1 and QoS 1.
- Broker port published only on `127.0.0.1:18883`.
- Anonymous access enabled solely inside this local test fixture.
- Synthetic canonical events only.

## Campaign sequence

1. Publish a retained synthetic event before the consumer connects.
2. Start a fresh persistent-session consumer and require ledger count one.
3. Publish the same event again and require a duplicate without another row.
4. Publish a second event and require durable acceptance.
5. Stop the Mosquitto container and observe an unexpected disconnect.
6. Restart the same container and volume and observe automatic reconnection.
7. Restore the persistent subscription without creating a second subscription.
8. Publish a third event and require ingestion to resume at count three.
9. Require zero callback and runtime rejections.

Manual acknowledgement occurs after the broker-neutral runtime returns. A
processing exception is recorded and deliberately left unacknowledged.
Connection-attempt failures are counted separately from processing errors so a
controlled outage does not misclassify evidence handling.

## Security and claim boundary

The configuration is intentionally unsuitable for deployment: it has no TLS or
authentication. Loopback binding limits host exposure during the test. This
campaign demonstrates interoperability and controlled reconnect behavior for
the pinned components, not production availability, security or hardware
reliability.

# Secure MQTT campaign v1.0

## Identities

All identities are synthetic and valid for two days:

| Certificate CN | Authorized action |
|---|---|
| `broker` | Present the verified `localhost` server identity |
| `edge-publisher` | Publish to `edge-evidence/v1/+/+` |
| `edge-consumer` | Subscribe to `edge-evidence/v1/+/+` |
| `rogue-client` | None; signed by an untrusted synthetic CA |

Private keys and certificates are generated beneath an ignored directory during
the test run. They are fixtures, not production credentials.

## Positive proof

1. Start Mosquitto with a TLS-only listener and mandatory client certificates.
2. Connect the Paho evidence consumer with the trusted read-only identity.
3. Publish a canonical synthetic event with the trusted writer identity.
4. Require durable ledger acceptance.

## Negative proof

1. Attempt TLS without a client certificate and require handshake rejection.
2. Attempt TLS with the rogue certificate and require handshake rejection.
3. Publish a different event with the trusted reader identity.
4. Require the ledger count to remain unchanged.
5. Publish that event with the writer identity and require acceptance.

## Claim boundary

This proves the configured trust and authorization decisions for an ephemeral
local PKI and pinned Mosquitto container. It does not prove production
certificate lifecycle management, secure key custody, revocation availability,
enterprise identity, network availability or device authenticity.

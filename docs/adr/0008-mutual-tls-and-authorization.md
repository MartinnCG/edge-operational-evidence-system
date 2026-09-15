# ADR-0008: Mutual-TLS identity and role authorization

- Status: Accepted
- Milestone: M8

## Context

The loopback-only M7 fixture intentionally permits anonymous clients and carries
unencrypted MQTT. A credible security boundary must prove server identity,
require client identity and prevent an authenticated client from exercising the
wrong role, without committing reusable secrets.

## Decision

Create a separate secure Mosquitto fixture. Generate a short-lived synthetic CA,
broker certificate and client certificates at test time. Require certificates
signed by that CA, verify the broker hostname, and map the client certificate CN
to the Mosquitto username. Apply a static ACL that grants `edge-publisher` write
access and `edge-consumer` read access only to `edge-evidence/v1/+/+`.
A separate `health-probe` identity may write only to `health/mqtt`, outside the
evidence hierarchy.

Paho receives explicit CA, client-certificate and private-key paths and always
sets `tls_insecure_set(False)`. The negative campaign attempts a connection with
no client certificate, a certificate signed by an untrusted CA, and publication
using the read-only consumer identity.

## Consequences

- Server and client authentication occur before MQTT evidence processing.
- Wrong-role publication cannot mutate the evidence ledger.
- No generated private key or certificate is committed to Git.
- The separate insecure M7 fixture remains an intentionally bounded transport
  and reconnect test.
- Production issuance, protected key storage, rotation, revocation and identity
  governance remain future requirements.

## References

- [Mosquitto authentication and TLS configuration](https://mosquitto.org/man/mosquitto-conf-5.html)
- [Eclipse Paho Python TLS client API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)

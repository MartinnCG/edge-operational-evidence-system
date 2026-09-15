"""Public package contract for Edge Operational Evidence System."""

from edge_evidence.about import SYSTEM_ID, SystemIdentity
from edge_evidence.event import (
    SCHEMA_VERSION,
    CanonicalEvent,
    EventValidationError,
)
from edge_evidence.ledger import (
    EventIdentityConflict,
    EventLedger,
    IngestResult,
    IngestStatus,
    LedgerIntegrityError,
    SourceSequenceConflict,
    StoredEvent,
)
from edge_evidence.mqtt import (
    MQTT_ADAPTER_VERSION,
    DeliveryDisposition,
    DeliveryResult,
    MqttAdapterError,
    MqttIngestionRuntime,
    RuntimeMetrics,
    event_to_mqtt,
    mqtt_to_event,
)
from edge_evidence.paho_consumer import (
    PAHO_CONSUMER_VERSION,
    BrokerConnectionError,
    PahoConsumerConfig,
    PahoMqttConsumer,
    PahoTlsConfig,
    PahoUnavailableError,
)
from edge_evidence.projection import (
    PROJECTOR_VERSION,
    ProjectionError,
    ProjectionResult,
    project_events,
    replay,
)
from edge_evidence.quality import (
    QUALITY_POLICY_VERSION,
    QualityFinding,
    QualityPolicy,
    Severity,
    evaluate_quality,
)
from edge_evidence.stream import StreamFinding, inspect_stream

__all__ = [
    "SCHEMA_VERSION",
    "SYSTEM_ID",
    "CanonicalEvent",
    "EventValidationError",
    "EventIdentityConflict",
    "EventLedger",
    "IngestResult",
    "IngestStatus",
    "LedgerIntegrityError",
    "MQTT_ADAPTER_VERSION",
    "MqttAdapterError",
    "MqttIngestionRuntime",
    "PAHO_CONSUMER_VERSION",
    "PahoConsumerConfig",
    "PahoMqttConsumer",
    "PahoTlsConfig",
    "PahoUnavailableError",
    "PROJECTOR_VERSION",
    "ProjectionError",
    "ProjectionResult",
    "QUALITY_POLICY_VERSION",
    "QualityFinding",
    "QualityPolicy",
    "Severity",
    "SourceSequenceConflict",
    "StreamFinding",
    "StoredEvent",
    "SystemIdentity",
    "DeliveryDisposition",
    "DeliveryResult",
    "RuntimeMetrics",
    "BrokerConnectionError",
    "__version__",
    "inspect_stream",
    "evaluate_quality",
    "event_to_mqtt",
    "mqtt_to_event",
    "project_events",
    "replay",
]

__version__ = "0.2.0.dev0"

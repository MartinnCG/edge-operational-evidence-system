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
    SourceSequenceConflict,
    StoredEvent,
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
    "SourceSequenceConflict",
    "StreamFinding",
    "StoredEvent",
    "SystemIdentity",
    "__version__",
    "inspect_stream",
]

__version__ = "0.1.0.dev0"

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
from edge_evidence.projection import (
    PROJECTOR_VERSION,
    ProjectionError,
    ProjectionResult,
    project_events,
    replay,
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
    "PROJECTOR_VERSION",
    "ProjectionError",
    "ProjectionResult",
    "SourceSequenceConflict",
    "StreamFinding",
    "StoredEvent",
    "SystemIdentity",
    "__version__",
    "inspect_stream",
    "project_events",
    "replay",
]

__version__ = "0.1.0.dev0"

"""Static system identity exposed during the M0 repository phase."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemIdentity:
    """Machine-readable statement of the current implementation boundary."""

    name: str
    development_phase: str
    runtime_behavior_available: bool


SYSTEM_ID = SystemIdentity(
    name="Edge Operational Evidence System",
    development_phase="M0",
    runtime_behavior_available=False,
)

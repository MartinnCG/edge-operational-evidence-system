"""Tests for the M0 public package contract."""

from edge_evidence import SYSTEM_ID, __version__


def test_development_version_is_explicit() -> None:
    assert __version__ == "0.1.0.dev0"


def test_system_identity_does_not_claim_runtime_capability() -> None:
    assert SYSTEM_ID.name == "Edge Operational Evidence System"
    assert SYSTEM_ID.development_phase == "M0"
    assert SYSTEM_ID.runtime_behavior_available is False

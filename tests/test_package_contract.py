"""Tests for the public package identity."""

from edge_evidence import SYSTEM_ID, __version__


def test_development_version_is_explicit() -> None:
    assert __version__ == "0.1.0.dev0"


def test_system_identity_declares_m3_boundary() -> None:
    assert SYSTEM_ID.name == "Edge Operational Evidence System"
    assert SYSTEM_ID.development_phase == "M3"
    assert SYSTEM_ID.runtime_behavior_available is True

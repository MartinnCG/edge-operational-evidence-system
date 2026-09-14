"""Atomic storage and fail-closed verification of replay checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from edge_evidence.projection import (
    PROJECTOR_VERSION,
    ProjectionResult,
    canonical_state_json,
)

CHECKPOINT_VERSION = "1.0"
_FIELDS = {
    "checkpoint_version",
    "last_ordinal",
    "projector_version",
    "state",
    "state_sha256",
}


class CheckpointError(RuntimeError):
    """A checkpoint rejected with a stable machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def checkpoint_mapping(result: ProjectionResult) -> dict[str, Any]:
    return {
        "checkpoint_version": CHECKPOINT_VERSION,
        "last_ordinal": result.state["last_ordinal"],
        "projector_version": result.state["projector_version"],
        "state": result.state,
        "state_sha256": result.state_sha256,
    }


def write_checkpoint(path: str | Path, result: ProjectionResult) -> None:
    """Write a checkpoint atomically and synchronize file contents."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        checkpoint_mapping(result),
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    descriptor, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_checkpoint(path: str | Path) -> ProjectionResult:
    """Load and verify checkpoint structure, version and state digest."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CheckpointError("unreadable_checkpoint", str(error)) from error
    if not isinstance(document, Mapping) or set(document) != _FIELDS:
        raise CheckpointError("invalid_checkpoint_structure", "unexpected fields")
    if document["checkpoint_version"] != CHECKPOINT_VERSION:
        raise CheckpointError("unsupported_checkpoint_version", "unsupported version")
    if document["projector_version"] != PROJECTOR_VERSION:
        raise CheckpointError("unsupported_projector_version", "unsupported projector")
    state = document["state"]
    if not isinstance(state, Mapping):
        raise CheckpointError("invalid_state", "state must be an object")
    if state.get("projector_version") != document["projector_version"]:
        raise CheckpointError("projector_version_mismatch", "projector mismatch")
    if state.get("last_ordinal") != document["last_ordinal"]:
        raise CheckpointError("ordinal_mismatch", "last ordinal mismatch")
    canonical = canonical_state_json(state)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != document["state_sha256"]:
        raise CheckpointError("state_digest_mismatch", "state digest mismatch")
    return ProjectionResult(state=state, canonical_json=canonical, state_sha256=digest)

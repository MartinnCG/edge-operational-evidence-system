"""Deterministic, evidence-linked data-quality policy."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from edge_evidence.ledger import StoredEvent

QUALITY_POLICY_VERSION = "1.0"


class Severity(StrEnum):
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    version: str = QUALITY_POLICY_VERSION
    delay_threshold_seconds: int = 60
    stale_after_seconds: int = 60
    frozen_run_length: int = 3

    def __post_init__(self) -> None:
        if self.version != QUALITY_POLICY_VERSION:
            raise ValueError(f"unsupported quality policy version: {self.version}")
        if self.delay_threshold_seconds < 0 or self.stale_after_seconds < 0:
            raise ValueError("time thresholds must be non-negative")
        if self.frozen_run_length < 2:
            raise ValueError("frozen_run_length must be at least 2")


@dataclass(frozen=True, slots=True)
class QualityFinding:
    finding_id: str
    code: str
    rule_id: str
    rule_version: str
    severity: Severity
    source_id: str
    event_ids: tuple[str, ...]
    ledger_ordinals: tuple[int, ...]
    evidence: Mapping[str, Any]
    interpretation: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "event_ids": list(self.event_ids),
            "evidence": dict(self.evidence),
            "finding_id": self.finding_id,
            "interpretation": self.interpretation,
            "ledger_ordinals": list(self.ledger_ordinals),
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "severity": self.severity.value,
            "source_id": self.source_id,
        }


def finding_identity_digest(finding: Mapping[str, Any]) -> str:
    """Recompute the deterministic identity bound by a finding document."""
    identity = {
        "code": finding["code"],
        "event_ids": finding["event_ids"],
        "evidence": finding["evidence"],
        "ledger_ordinals": finding["ledger_ordinals"],
        "rule_id": finding["rule_id"],
        "rule_version": finding["rule_version"],
        "source_id": finding["source_id"],
    }
    canonical = json.dumps(identity, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _finding(
    *,
    code: str,
    rule_id: str,
    source_id: str,
    events: Iterable[StoredEvent],
    evidence: Mapping[str, Any],
    interpretation: str,
) -> QualityFinding:
    supporting = tuple(events)
    event_ids = tuple(item.event.event_id for item in supporting)
    ordinals = tuple(item.ordinal for item in supporting)
    identity = {
        "code": code,
        "event_ids": event_ids,
        "evidence": evidence,
        "ledger_ordinals": ordinals,
        "rule_id": rule_id,
        "rule_version": QUALITY_POLICY_VERSION,
        "source_id": source_id,
    }
    return QualityFinding(
        finding_id=finding_identity_digest(identity),
        code=code,
        rule_id=rule_id,
        rule_version=QUALITY_POLICY_VERSION,
        severity=Severity.WARNING,
        source_id=source_id,
        event_ids=event_ids,
        ledger_ordinals=ordinals,
        evidence=dict(evidence),
        interpretation=interpretation,
    )


def evaluate_quality(
    stored_events: Iterable[StoredEvent],
    *,
    as_of: datetime,
    policy: QualityPolicy | None = None,
) -> tuple[QualityFinding, ...]:
    """Evaluate generic evidence quality without reading the system clock."""
    active = policy or QualityPolicy()
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("as_of must use UTC")
    as_of = as_of.astimezone(UTC)
    rows = tuple(stored_events)
    by_source: dict[str, list[StoredEvent]] = defaultdict(list)
    findings: list[QualityFinding] = []

    highest_in_append_order: dict[str, StoredEvent] = {}
    for row in rows:
        event = row.event
        by_source[event.source_id].append(row)
        delay = event.ingested_at - event.observed_at
        if delay.total_seconds() > active.delay_threshold_seconds:
            findings.append(
                _finding(
                    code="delayed_arrival",
                    rule_id="DQ-001",
                    source_id=event.source_id,
                    events=(row,),
                    evidence={"delay_seconds": delay.total_seconds()},
                    interpretation="Arrival exceeded the configured evidence delay.",
                )
            )
        previous = highest_in_append_order.get(event.source_id)
        if previous and event.source_sequence < previous.event.source_sequence:
            findings.append(
                _finding(
                    code="source_sequence_regression",
                    rule_id="DQ-003",
                    source_id=event.source_id,
                    events=(previous, row),
                    evidence={
                        "current_sequence": event.source_sequence,
                        "prior_highest_sequence": previous.event.source_sequence,
                    },
                    interpretation="Append arrival order regressed in source sequence.",
                )
            )
        if previous is None or event.source_sequence > previous.event.source_sequence:
            highest_in_append_order[event.source_id] = row

    for source_id, source_rows in sorted(by_source.items()):
        ordered = sorted(source_rows, key=lambda row: row.event.source_sequence)
        for left, right in zip(ordered, ordered[1:], strict=False):
            missing = right.event.source_sequence - left.event.source_sequence - 1
            if missing > 0:
                findings.append(
                    _finding(
                        code="source_sequence_gap",
                        rule_id="DQ-002",
                        source_id=source_id,
                        events=(left, right),
                        evidence={
                            "missing_count": missing,
                            "missing_from": left.event.source_sequence + 1,
                            "missing_to": right.event.source_sequence - 1,
                        },
                        interpretation="One or more source positions lack evidence.",
                    )
                )

        runs: list[list[StoredEvent]] = []
        current_run: list[StoredEvent] = []
        prior_payload: str | None = None
        for row in ordered:
            payload = json.dumps(
                row.event.payload, separators=(",", ":"), sort_keys=True
            )
            if payload == prior_payload:
                current_run.append(row)
            else:
                if current_run:
                    runs.append(current_run)
                current_run = [row]
                prior_payload = payload
        if current_run:
            runs.append(current_run)
        for run in runs:
            if len(run) >= active.frozen_run_length:
                payload_bytes = json.dumps(
                    run[0].event.payload, separators=(",", ":"), sort_keys=True
                ).encode()
                findings.append(
                    _finding(
                        code="repeated_payload_run",
                        rule_id="DQ-004",
                        source_id=source_id,
                        events=run,
                        evidence={
                            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                            "run_length": len(run),
                        },
                        interpretation=(
                            "Repeated values require review; "
                            "sensor failure is not inferred."
                        ),
                    )
                )

        latest = ordered[-1]
        age = as_of - latest.event.observed_at
        if age.total_seconds() > active.stale_after_seconds:
            findings.append(
                _finding(
                    code="stale_source",
                    rule_id="DQ-005",
                    source_id=source_id,
                    events=(latest,),
                    evidence={"age_seconds": age.total_seconds()},
                    interpretation=(
                        "No recent observation exists at the evaluation time."
                    ),
                )
            )

    return tuple(sorted(findings, key=lambda finding: finding.finding_id))

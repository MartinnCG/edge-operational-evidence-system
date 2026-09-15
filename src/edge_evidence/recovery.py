"""Controlled process-restart and MQTT redelivery campaign."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edge_evidence.bundle import build_bundle, verify_bundle
from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.mqtt import MqttIngestionRuntime, event_to_mqtt
from edge_evidence.projection import replay
from edge_evidence.simulator import SimulatorConfig, generate_records

RECOVERY_CAMPAIGN_VERSION = "1.0"
CRASH_EXIT_CODE = 91
DEFAULT_CREATED_AT = datetime(2026, 1, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecoveryCampaignResult:
    bundle_path: Path
    bundle_valid: bool
    child_exit_code: int
    committed_before_restart: int
    event_count: int
    recovered_state_sha256: str
    reference_state_sha256: str
    runtime_metrics: dict[str, int]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "bundle_path": str(self.bundle_path),
            "bundle_valid": self.bundle_valid,
            "campaign_version": RECOVERY_CAMPAIGN_VERSION,
            "child_exit_code": self.child_exit_code,
            "committed_before_restart": self.committed_before_restart,
            "event_count": self.event_count,
            "recovered_state_sha256": self.recovered_state_sha256,
            "reference_state_sha256": self.reference_state_sha256,
            "runtime_metrics": self.runtime_metrics,
        }


def _records(seed: int, count: int) -> list[CanonicalEvent]:
    return [
        CanonicalEvent.from_mapping(record)
        for record in generate_records(SimulatorConfig(seed=seed, count=count))
    ]


def _deliver(
    runtime: MqttIngestionRuntime,
    event: CanonicalEvent,
    *,
    received_at: datetime | None = None,
) -> None:
    topic, payload = event_to_mqtt(event)
    result = runtime.ingest(
        topic, payload, received_at=received_at or event.ingested_at
    )
    if result.rejection_code is not None:
        raise RuntimeError(f"synthetic delivery rejected: {result.rejection_code}")


def _crash_worker(ledger_path: Path, *, seed: int, count: int, stop: int) -> None:
    ledger = EventLedger(ledger_path)
    runtime = MqttIngestionRuntime(ledger)
    for event in _records(seed, count)[:stop]:
        _deliver(runtime, event)
    os._exit(CRASH_EXIT_CODE)


def run_recovery_campaign(
    workspace: str | Path,
    *,
    seed: int = 2026,
    count: int = 8,
    crash_after: int = 4,
) -> RecoveryCampaignResult:
    """Crash after committed writes, reopen, redeliver and verify convergence."""
    if count < 2:
        raise ValueError("count must be at least 2")
    if not 1 <= crash_after < count:
        raise ValueError("crash_after must be between 1 and count - 1")
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=False)
    ledger_path = root / "edge-ledger.sqlite3"
    bundle_path = root / "recovered-evidence"
    events = _records(seed, count)

    with EventLedger(":memory:") as reference_ledger:
        reference_runtime = MqttIngestionRuntime(reference_ledger)
        for index, event in enumerate(events):
            received_at = (
                event.ingested_at
                if index < crash_after
                else event.ingested_at + timedelta(minutes=5)
            )
            _deliver(reference_runtime, event, received_at=received_at)
        reference_digest = replay(reference_ledger).state_sha256

    command = [
        sys.executable,
        "-m",
        "edge_evidence.recovery",
        "_crash-worker",
        "--ledger",
        str(ledger_path),
        "--seed",
        str(seed),
        "--count",
        str(count),
        "--crash-after",
        str(crash_after),
    ]
    child = subprocess.run(command, check=False)
    if child.returncode != CRASH_EXIT_CODE:
        raise RuntimeError(f"crash worker returned {child.returncode}")

    with EventLedger(ledger_path) as recovered_ledger:
        committed = recovered_ledger.count()
        runtime = MqttIngestionRuntime(recovered_ledger)
        runtime.record_disconnect()
        runtime.record_reconnect()
        for event in events:
            _deliver(
                runtime,
                event,
                received_at=event.ingested_at + timedelta(minutes=5),
            )
        recovered = replay(recovered_ledger)
        if recovered.state_sha256 != reference_digest:
            raise RuntimeError("recovered state does not match uninterrupted reference")
        build_bundle(
            recovered_ledger,
            bundle_path,
            bundle_id="m6-controlled-recovery",
            created_at=DEFAULT_CREATED_AT,
            as_of=events[-1].ingested_at + timedelta(minutes=6),
            scenario="mqtt-controlled-restart",
            seed=seed,
        )
        event_count = recovered_ledger.count()
        metrics = runtime.metrics.to_mapping()
    verification = verify_bundle(bundle_path)
    return RecoveryCampaignResult(
        bundle_path=bundle_path,
        bundle_valid=verification.valid,
        child_exit_code=child.returncode,
        committed_before_restart=committed,
        event_count=event_count,
        recovered_state_sha256=recovered.state_sha256,
        reference_state_sha256=reference_digest,
        runtime_metrics=metrics,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled recovery proof")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--seed", type=int, default=2026)
    run.add_argument("--count", type=int, default=8)
    run.add_argument("--crash-after", type=int, default=4)
    worker = subparsers.add_parser("_crash-worker")
    worker.add_argument("--ledger", type=Path, required=True)
    worker.add_argument("--seed", type=int, required=True)
    worker.add_argument("--count", type=int, required=True)
    worker.add_argument("--crash-after", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "_crash-worker":
        _crash_worker(
            args.ledger,
            seed=args.seed,
            count=args.count,
            stop=args.crash_after,
        )
        return 0
    result = run_recovery_campaign(
        args.workspace,
        seed=args.seed,
        count=args.count,
        crash_after=args.crash_after,
    )
    print(json.dumps(result.to_mapping(), sort_keys=True))
    return 0 if result.bundle_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

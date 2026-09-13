"""Seeded synthetic event and fault simulator."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from edge_evidence.event import CanonicalEvent

_ID_NAMESPACE = uuid.UUID("36d5ba58-30a8-4bcf-a68b-d9adbbf6de23")


class Scenario(StrEnum):
    BASELINE = "baseline"
    DELAYED = "delayed"
    DUPLICATE = "duplicate"
    REORDERED = "reordered"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    seed: int = 42
    count: int = 10
    source_id: str = "sensor.synthetic-001"
    start_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    interval_seconds: int = 10
    scenario: Scenario = Scenario.BASELINE

    def __post_init__(self) -> None:
        if self.count < 2:
            raise ValueError("count must be at least 2")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.start_at.tzinfo is None or self.start_at.utcoffset() != timedelta(0):
            raise ValueError("start_at must use UTC")


def generate_records(config: SimulatorConfig) -> list[dict[str, Any]]:
    """Generate deterministic synthetic records for the selected scenario."""
    rng = random.Random(config.seed)
    records: list[dict[str, Any]] = []
    for sequence in range(config.count):
        observed = config.start_at + timedelta(
            seconds=sequence * config.interval_seconds
        )
        event_id = str(
            uuid.uuid5(
                _ID_NAMESPACE,
                f"{config.seed}:{config.source_id}:{sequence}:{observed.isoformat()}",
            )
        )
        event = CanonicalEvent(
            event_id=event_id,
            source_id=config.source_id,
            source_sequence=sequence,
            event_type="environment.sample",
            observed_at=observed,
            ingested_at=observed + timedelta(seconds=1),
            payload={
                "humidity_pct": round(48.0 + rng.uniform(-3.0, 3.0), 3),
                "temperature_c": round(22.0 + rng.uniform(-1.5, 1.5), 3),
            },
            metadata={"generator": "deterministic-simulator", "synthetic": True},
        )
        records.append(event.to_mapping())

    pivot = config.count // 2
    if config.scenario is Scenario.DELAYED:
        observed = CanonicalEvent.from_mapping(records[pivot]).observed_at
        records[pivot]["ingested_at"] = (
            observed + timedelta(seconds=120)
        ).isoformat(timespec="microseconds").replace("+00:00", "Z")
    elif config.scenario is Scenario.DUPLICATE:
        records.insert(pivot + 1, dict(records[pivot]))
    elif config.scenario is Scenario.REORDERED:
        records[pivot], records[pivot + 1] = records[pivot + 1], records[pivot]
    elif config.scenario is Scenario.MALFORMED:
        records[pivot] = dict(records[pivot])
        records[pivot]["schema_version"] = "999.0"
    return records


def canonical_jsonl(records: Sequence[dict[str, Any]]) -> bytes:
    """Serialize mappings into stable UTF-8 JSONL, including invalid fixtures."""
    lines = [
        json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for record in records
    ]
    return ("\n".join(lines) + "\n").encode()


def sha256_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic edge event JSONL")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--scenario", choices=list(Scenario), default=Scenario.BASELINE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    config = SimulatorConfig(
        seed=args.seed, count=args.count, scenario=Scenario(args.scenario)
    )
    content = canonical_jsonl(generate_records(config))
    if args.output:
        args.output.write_bytes(content)
    else:
        print(content.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

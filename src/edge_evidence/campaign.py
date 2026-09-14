"""Deterministic synthetic data-quality failure campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from edge_evidence.event import CanonicalEvent, EventValidationError
from edge_evidence.ledger import EventLedger, IngestStatus
from edge_evidence.quality import QualityFinding, QualityPolicy, evaluate_quality
from edge_evidence.simulator import (
    Scenario,
    SimulatorConfig,
    generate_records,
)
from edge_evidence.stream import inspect_stream

CAMPAIGN_VERSION = "1.0"
BOUNDARY_CLASSIFIER_VERSION = "1.0"


class CampaignScenario(StrEnum):
    BASELINE = "baseline"
    DELAYED = "delayed"
    DUPLICATE = "duplicate"
    REORDERED = "reordered"
    MALFORMED = "malformed"
    MISSING = "missing"
    STALE = "stale"
    FROZEN = "frozen"


@dataclass(frozen=True, slots=True)
class CampaignResult:
    scenario: CampaignScenario
    seed: int
    input_count: int
    accepted_count: int
    duplicate_count: int
    invalid_count: int
    detected_codes: tuple[str, ...]
    boundary_findings: tuple[dict[str, Any], ...]
    quality_findings: tuple[QualityFinding, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "accepted_count": self.accepted_count,
            "boundary_findings": list(self.boundary_findings),
            "campaign_version": CAMPAIGN_VERSION,
            "detected_codes": list(self.detected_codes),
            "duplicate_count": self.duplicate_count,
            "input_count": self.input_count,
            "invalid_count": self.invalid_count,
            "quality_findings": [item.to_mapping() for item in self.quality_findings],
            "scenario": self.scenario.value,
            "seed": self.seed,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_mapping(), separators=(",", ":"), sort_keys=True)

    def sha256_digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def campaign_records(
    scenario: CampaignScenario, seed: int
) -> list[dict[str, Any]]:
    mapped = {
        CampaignScenario.BASELINE: Scenario.BASELINE,
        CampaignScenario.DELAYED: Scenario.DELAYED,
        CampaignScenario.DUPLICATE: Scenario.DUPLICATE,
        CampaignScenario.REORDERED: Scenario.REORDERED,
        CampaignScenario.MALFORMED: Scenario.MALFORMED,
    }
    if scenario in mapped:
        return generate_records(
            SimulatorConfig(seed=seed, count=8, scenario=mapped[scenario])
        )
    records = generate_records(SimulatorConfig(seed=seed, count=8))
    pivot = len(records) // 2
    if scenario is CampaignScenario.MISSING:
        records.pop(pivot)
    elif scenario is CampaignScenario.FROZEN:
        repeated = dict(records[pivot - 1]["payload"])
        for index in range(pivot - 1, pivot + 2):
            records[index]["payload"] = dict(repeated)
    return records


def run_campaign(
    scenario: CampaignScenario, *, seed: int = 2026
) -> CampaignResult:
    records = campaign_records(scenario, seed)
    inspected = inspect_stream(records)
    boundary = tuple(
        {
            "classifier_version": BOUNDARY_CLASSIFIER_VERSION,
            "code": item.code,
            "event_id": item.event_id,
            "record_index": item.record_index,
        }
        for item in inspected
    )
    accepted = 0
    duplicates = 0
    invalid = 0
    with EventLedger(":memory:") as ledger:
        for record in records:
            try:
                event = CanonicalEvent.from_mapping(record)
            except EventValidationError:
                invalid += 1
                continue
            result = ledger.ingest(event)
            if result.status is IngestStatus.ACCEPTED:
                accepted += 1
            else:
                duplicates += 1
        latest_observed = max(
            (item.event.observed_at for item in ledger.read_events()),
            default=SimulatorConfig().start_at,
        )
        extra_age = 120 if scenario is CampaignScenario.STALE else 1
        as_of = latest_observed + timedelta(seconds=extra_age)
        quality = evaluate_quality(
            ledger.read_events(), as_of=as_of, policy=QualityPolicy()
        )
    codes = tuple(
        sorted({item["code"] for item in boundary} | {item.code for item in quality})
    )
    return CampaignResult(
        scenario=scenario,
        seed=seed,
        input_count=len(records),
        accepted_count=accepted,
        duplicate_count=duplicates,
        invalid_count=invalid,
        detected_codes=codes,
        boundary_findings=boundary,
        quality_findings=quality,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic synthetic quality campaign"
    )
    parser.add_argument("scenario", choices=list(CampaignScenario))
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_campaign(CampaignScenario(args.scenario), seed=args.seed)
    document = result.to_mapping()
    document["result_sha256"] = result.sha256_digest()
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

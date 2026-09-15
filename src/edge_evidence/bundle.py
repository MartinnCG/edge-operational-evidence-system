"""Deterministic evidence-bundle construction and independent verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edge_evidence.campaign import (
    CampaignScenario,
    campaign_records,
    run_campaign,
)
from edge_evidence.event import SCHEMA_VERSION, CanonicalEvent, EventValidationError
from edge_evidence.ledger import (
    LEDGER_SCHEMA_VERSION,
    EventLedger,
    IngestStatus,
)
from edge_evidence.projection import (
    PROJECTOR_VERSION,
    canonical_state_json,
    replay,
)
from edge_evidence.quality import (
    QUALITY_POLICY_VERSION,
    QualityPolicy,
    evaluate_quality,
    finding_identity_digest,
)

BUNDLE_VERSION = "1.0"
SYSTEM_VERSION = "0.1.0"

_PAYLOAD_FILES = (
    "boundary_findings.jsonl",
    "ledger_events.jsonl",
    "policy.json",
    "quality_findings.jsonl",
    "report.md",
    "run.json",
    "state.json",
)
_SEALED_FILES = (*_PAYLOAD_FILES, "manifest.json")
_EXPECTED_FILES = {*_SEALED_FILES, "checksums.sha256"}
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {
    "boundary_findings.jsonl": "application/x-ndjson",
    "ledger_events.jsonl": "application/x-ndjson",
    "policy.json": "application/json",
    "quality_findings.jsonl": "application/x-ndjson",
    "report.md": "text/markdown; charset=utf-8",
    "run.json": "application/json",
    "state.json": "application/json",
}
_LEDGER_FIELDS = {"content_sha256", "event", "ordinal"}
_QUALITY_FIELDS = {
    "code",
    "event_ids",
    "evidence",
    "finding_id",
    "interpretation",
    "ledger_ordinals",
    "rule_id",
    "rule_version",
    "severity",
    "source_id",
}
_BOUNDARY_FIELDS = {
    "classifier_version",
    "code",
    "event_id",
    "record_index",
}


class BundleExistsError(FileExistsError):
    """The requested write-once bundle target already exists."""


@dataclass(frozen=True, slots=True)
class BundleBuildResult:
    path: Path
    bundle_id: str
    manifest_sha256: str
    file_count: int


@dataclass(frozen=True, slots=True)
class BundleVerification:
    valid: bool
    bundle_id: str | None
    checked_files: int
    errors: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "checked_files": self.checked_files,
            "errors": list(self.errors),
            "valid": self.valid,
            "verification_version": BUNDLE_VERSION,
        }


def _utc(value: datetime, field: str) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _jsonl_bytes(values: Sequence[Mapping[str, Any]]) -> bytes:
    if not values:
        return b""
    return b"".join(_json_bytes(value) for value in values)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _report(run: Mapping[str, Any], codes: Sequence[str]) -> bytes:
    counts = Counter(codes)
    finding_lines = (
        [f"- `{code}`: {counts[code]}" for code in sorted(counts)]
        if counts
        else ["- No findings in this synthetic run."]
    )
    lines = [
        "# Operational Evidence Report",
        "",
        f"- Bundle: `{run['bundle_id']}`",
        f"- Scenario: `{run['scenario'] or 'unspecified'}`",
        f"- Created at: `{run['created_at']}`",
        f"- Evaluated as of: `{run['evaluated_as_of']}`",
        f"- Accepted events: {run['event_count']}",
        f"- Quality findings: {run['quality_finding_count']}",
        f"- Boundary findings: {run['boundary_finding_count']}",
        f"- State SHA-256: `{run['state_sha256']}`",
        "",
        "## Finding summary",
        "",
        *finding_lines,
        "",
        "## Integrity status",
        "",
        "Bundle sealed; independent verification required.",
        "",
        "## Interpretation boundary",
        "",
        "Findings describe evidence conditions for human review. They do not",
        "certify sensor accuracy, diagnose physical failure, issue a safety alarm,",
        "or instruct operation of equipment.",
        "",
    ]
    return "\n".join(lines).encode()


def build_bundle(
    ledger: EventLedger,
    output: str | Path,
    *,
    bundle_id: str,
    created_at: datetime,
    as_of: datetime,
    policy: QualityPolicy | None = None,
    boundary_findings: Sequence[Mapping[str, Any]] = (),
    scenario: str | None = None,
    seed: int | None = None,
) -> BundleBuildResult:
    """Build a complete bundle in a temporary directory, then rename it once."""
    target = Path(output)
    if target.exists():
        raise BundleExistsError(f"bundle target already exists: {target}")
    if not bundle_id or any(character in bundle_id for character in "/\\"):
        raise ValueError("bundle_id must be a non-empty portable identifier")
    created_text = _utc(created_at, "created_at")
    as_of_text = _utc(as_of, "as_of")
    active_policy = policy or QualityPolicy()
    rows = ledger.read_events()
    projection = replay(ledger)
    quality = evaluate_quality(rows, as_of=as_of, policy=active_policy)

    ledger_documents = tuple(
        {
            "content_sha256": row.content_sha256,
            "event": row.event.to_mapping(),
            "ordinal": row.ordinal,
        }
        for row in rows
    )
    quality_documents = tuple(item.to_mapping() for item in quality)
    boundary_documents = tuple(
        sorted((dict(item) for item in boundary_findings), key=_sort_mapping)
    )
    policy_document = {
        "delay_threshold_seconds": active_policy.delay_threshold_seconds,
        "frozen_run_length": active_policy.frozen_run_length,
        "stale_after_seconds": active_policy.stale_after_seconds,
        "version": active_policy.version,
    }
    all_codes = [item["code"] for item in boundary_documents]
    all_codes.extend(item["code"] for item in quality_documents)
    run_document = {
        "boundary_finding_count": len(boundary_documents),
        "bundle_id": bundle_id,
        "bundle_version": BUNDLE_VERSION,
        "created_at": created_text,
        "evaluated_as_of": as_of_text,
        "event_contract_version": SCHEMA_VERSION,
        "event_count": len(rows),
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "projector_version": PROJECTOR_VERSION,
        "quality_finding_count": len(quality_documents),
        "quality_policy_version": QUALITY_POLICY_VERSION,
        "scenario": scenario,
        "seed": seed,
        "state_sha256": projection.state_sha256,
        "system_version": SYSTEM_VERSION,
    }
    payloads = {
        "boundary_findings.jsonl": _jsonl_bytes(boundary_documents),
        "ledger_events.jsonl": _jsonl_bytes(ledger_documents),
        "policy.json": _json_bytes(policy_document),
        "quality_findings.jsonl": _jsonl_bytes(quality_documents),
        "report.md": _report(run_document, all_codes),
        "run.json": _json_bytes(run_document),
        "state.json": (projection.canonical_json + "\n").encode(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for name, content in payloads.items():
            (temporary / name).write_bytes(content)
        manifest = {
            "artifacts": {
                name: {
                    "bytes": len(payloads[name]),
                    "media_type": _MEDIA_TYPES[name],
                    "sha256": _sha256(payloads[name]),
                }
                for name in sorted(payloads)
            },
            "bundle_id": bundle_id,
            "bundle_version": BUNDLE_VERSION,
        }
        manifest_bytes = _json_bytes(manifest)
        (temporary / "manifest.json").write_bytes(manifest_bytes)
        sealed = {**payloads, "manifest.json": manifest_bytes}
        checksum_bytes = "".join(
            f"{_sha256(sealed[name])}  {name}\n" for name in sorted(sealed)
        ).encode()
        (temporary / "checksums.sha256").write_bytes(checksum_bytes)
        os.rename(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return BundleBuildResult(
        path=target,
        bundle_id=bundle_id,
        manifest_sha256=_sha256(manifest_bytes),
        file_count=len(_EXPECTED_FILES),
    )


def _sort_mapping(value: Mapping[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def build_campaign_bundle(
    scenario: CampaignScenario,
    output: str | Path,
    *,
    bundle_id: str,
    created_at: datetime,
    seed: int = 2026,
) -> BundleBuildResult:
    """Build a public demonstration bundle entirely from synthetic data."""
    records = campaign_records(scenario, seed)
    campaign = run_campaign(scenario, seed=seed)
    with EventLedger(":memory:") as ledger:
        for record in records:
            try:
                event = CanonicalEvent.from_mapping(record)
            except EventValidationError:
                continue
            result = ledger.ingest(event)
            if result.status is IngestStatus.DUPLICATE:
                continue
        latest = max(
            (row.event.observed_at for row in ledger.read_events()),
            default=SimulatorDefaults.START_AT,
        )
        age = 120 if scenario is CampaignScenario.STALE else 1
        return build_bundle(
            ledger,
            output,
            bundle_id=bundle_id,
            created_at=created_at,
            as_of=latest + timedelta(seconds=age),
            boundary_findings=campaign.boundary_findings,
            scenario=scenario.value,
            seed=seed,
        )


class SimulatorDefaults:
    START_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _parse_json_file(path: Path, errors: list[str]) -> Any | None:
    try:
        content = path.read_bytes()
        value = json.loads(content)
    except (OSError, json.JSONDecodeError):
        errors.append(f"invalid_json:{path.name}")
        return None
    if content != _json_bytes(value):
        errors.append(f"noncanonical_json:{path.name}")
    return value


def _parse_jsonl(path: Path, errors: list[str]) -> list[Any]:
    try:
        content = path.read_bytes()
    except OSError:
        errors.append(f"unreadable:{path.name}")
        return []
    if not content:
        return []
    values: list[Any] = []
    for line in content.splitlines(keepends=True):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid_jsonl:{path.name}")
            return []
        if line != _json_bytes(value):
            errors.append(f"noncanonical_jsonl:{path.name}")
        values.append(value)
    return values


def _parse_checksums(content: bytes, errors: list[str]) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = content.decode().splitlines()
    except UnicodeDecodeError:
        errors.append("invalid_checksums_encoding")
        return entries
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _HEX_DIGEST.fullmatch(parts[0]):
            errors.append("invalid_checksum_line")
            continue
        digest, name = parts
        if name in entries or "/" in name or "\\" in name:
            errors.append("invalid_checksum_path")
            continue
        entries[name] = digest
    canonical = "".join(f"{entries[name]}  {name}\n" for name in sorted(entries))
    if not errors and content != canonical.encode():
        errors.append("noncanonical_checksums")
    return entries


def verify_bundle(path: str | Path) -> BundleVerification:
    """Independently verify sealing, canonical bytes and semantic links."""
    root = Path(path)
    errors: list[str] = []
    bundle_id: str | None = None
    if not root.is_dir():
        return BundleVerification(False, None, 0, ("bundle_not_directory",))
    actual_files = {item.name for item in root.iterdir() if item.is_file()}
    for name in sorted(_EXPECTED_FILES - actual_files):
        errors.append(f"missing_file:{name}")
    for name in sorted(actual_files - _EXPECTED_FILES):
        errors.append(f"unexpected_file:{name}")
    if errors:
        return BundleVerification(False, None, 0, tuple(errors))

    checksums = _parse_checksums((root / "checksums.sha256").read_bytes(), errors)
    if set(checksums) != set(_SEALED_FILES):
        errors.append("checksum_file_set_mismatch")
    for name in _SEALED_FILES:
        if checksums.get(name) != _sha256((root / name).read_bytes()):
            errors.append(f"checksum_mismatch:{name}")

    manifest = _parse_json_file(root / "manifest.json", errors)
    run = _parse_json_file(root / "run.json", errors)
    state = _parse_json_file(root / "state.json", errors)
    policy = _parse_json_file(root / "policy.json", errors)
    ledger_documents = _parse_jsonl(root / "ledger_events.jsonl", errors)
    quality_documents = _parse_jsonl(root / "quality_findings.jsonl", errors)
    boundary_documents = _parse_jsonl(root / "boundary_findings.jsonl", errors)

    if isinstance(manifest, Mapping):
        bundle_id = manifest.get("bundle_id")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, Mapping):
            errors.append("invalid_manifest_artifacts")
        elif set(artifacts) != set(_PAYLOAD_FILES):
            errors.append("manifest_file_set_mismatch")
        else:
            for name in _PAYLOAD_FILES:
                content = (root / name).read_bytes()
                entry = artifacts[name]
                if not isinstance(entry, Mapping):
                    errors.append(f"invalid_manifest_entry:{name}")
                    continue
                if set(entry) != {"bytes", "media_type", "sha256"}:
                    errors.append(f"invalid_manifest_entry:{name}")
                if entry.get("bytes") != len(content):
                    errors.append(f"size_mismatch:{name}")
                if entry.get("sha256") != _sha256(content):
                    errors.append(f"manifest_hash_mismatch:{name}")
                if entry.get("media_type") != _MEDIA_TYPES[name]:
                    errors.append(f"media_type_mismatch:{name}")
        if manifest.get("bundle_version") != BUNDLE_VERSION:
            errors.append("unsupported_bundle_version")
    else:
        errors.append("invalid_manifest")

    ordinal_to_event: dict[int, str] = {}
    prior_ordinal = 0
    for document in ledger_documents:
        try:
            if not isinstance(document, Mapping) or set(document) != _LEDGER_FIELDS:
                raise TypeError
            ordinal = document["ordinal"]
            event = CanonicalEvent.from_mapping(document["event"])
            digest = _sha256(event.canonical_json().encode())
            if document["content_sha256"] != digest:
                errors.append("ledger_content_digest_mismatch")
            if not isinstance(ordinal, int) or ordinal <= prior_ordinal:
                errors.append("ledger_ordinal_order_invalid")
            else:
                ordinal_to_event[ordinal] = event.event_id
                prior_ordinal = ordinal
        except (KeyError, TypeError, EventValidationError):
            errors.append("invalid_ledger_document")

    for finding in quality_documents:
        try:
            if not isinstance(finding, Mapping) or set(finding) != _QUALITY_FIELDS:
                raise TypeError
            if finding["finding_id"] != finding_identity_digest(finding):
                errors.append("finding_identity_mismatch")
            pairs = zip(
                finding["ledger_ordinals"], finding["event_ids"], strict=True
            )
            reference_mismatch = any(
                ordinal_to_event.get(ordinal) != event_id
                for ordinal, event_id in pairs
            )
            if reference_mismatch:
                errors.append("finding_event_reference_mismatch")
        except (KeyError, TypeError, ValueError):
            errors.append("invalid_quality_finding")

    for finding in boundary_documents:
        if not isinstance(finding, Mapping) or set(finding) != _BOUNDARY_FIELDS:
            errors.append("invalid_boundary_finding")
            continue
        if finding.get("classifier_version") != "1.0":
            errors.append("boundary_classifier_version_mismatch")
        if not isinstance(finding.get("record_index"), int):
            errors.append("invalid_boundary_finding")

    if isinstance(state, Mapping):
        state_digest = _sha256(canonical_state_json(state).encode())
        if isinstance(run, Mapping) and run.get("state_sha256") != state_digest:
            errors.append("state_digest_mismatch")
        expected_last = max(ordinal_to_event, default=0)
        if state.get("event_count") != len(ledger_documents):
            errors.append("state_event_count_mismatch")
        if state.get("last_ordinal") != expected_last:
            errors.append("state_last_ordinal_mismatch")
    else:
        errors.append("invalid_state")

    if isinstance(run, Mapping):
        if run.get("bundle_id") != bundle_id:
            errors.append("bundle_id_mismatch")
        if run.get("event_count") != len(ledger_documents):
            errors.append("run_event_count_mismatch")
        if run.get("quality_finding_count") != len(quality_documents):
            errors.append("run_quality_count_mismatch")
        if run.get("boundary_finding_count") != len(boundary_documents):
            errors.append("run_boundary_count_mismatch")
        if run.get("projector_version") != PROJECTOR_VERSION:
            errors.append("projector_version_mismatch")
        if run.get("quality_policy_version") != QUALITY_POLICY_VERSION:
            errors.append("quality_policy_version_mismatch")
    else:
        errors.append("invalid_run")
    if isinstance(policy, Mapping):
        if policy.get("version") != QUALITY_POLICY_VERSION:
            errors.append("policy_version_mismatch")
        threshold_fields = (
            "delay_threshold_seconds",
            "frozen_run_length",
            "stale_after_seconds",
        )
        if any(not isinstance(policy.get(field), int) for field in threshold_fields):
            errors.append("invalid_policy")
    else:
        errors.append("invalid_policy")

    return BundleVerification(
        valid=not errors,
        bundle_id=bundle_id,
        checked_files=len(_EXPECTED_FILES),
        errors=tuple(sorted(set(errors))),
    )


def _parse_utc_argument(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("timestamp must use UTC")
    return parsed.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify evidence bundles")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("build-demo")
    demo.add_argument("scenario", choices=list(CampaignScenario))
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--bundle-id", required=True)
    demo.add_argument("--seed", type=int, default=2026)
    demo.add_argument(
        "--created-at",
        type=_parse_utc_argument,
        default=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )
    verify = subparsers.add_parser("verify")
    verify.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "build-demo":
        result = build_campaign_bundle(
            CampaignScenario(args.scenario),
            args.output,
            bundle_id=args.bundle_id,
            created_at=args.created_at,
            seed=args.seed,
        )
        print(
            json.dumps(
                {
                    "bundle_id": result.bundle_id,
                    "file_count": result.file_count,
                    "manifest_sha256": result.manifest_sha256,
                    "status": "sealed",
                },
                sort_keys=True,
            )
        )
        return 0
    result = verify_bundle(args.path)
    print(json.dumps(result.to_mapping(), sort_keys=True))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

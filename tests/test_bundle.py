"""Build, sealing, semantic verification and tamper tests for M5."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from edge_evidence.bundle import (
    BundleExistsError,
    build_campaign_bundle,
    main,
    verify_bundle,
)
from edge_evidence.campaign import CampaignScenario

CREATED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _build(tmp_path, name="bundle"):
    path = tmp_path / name
    build_campaign_bundle(
        CampaignScenario.MISSING,
        path,
        bundle_id="bundle-synthetic-missing-001",
        created_at=CREATED_AT,
        seed=2026,
    )
    return path


def _files(path):
    return {item.name: item.read_bytes() for item in path.iterdir()}


def _canonical(value) -> bytes:
    return (
        json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _reseal(path) -> None:
    payload_names = {
        "boundary_findings.jsonl",
        "ledger_events.jsonl",
        "policy.json",
        "quality_findings.jsonl",
        "report.md",
        "run.json",
        "state.json",
    }
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in payload_names:
        content = (path / name).read_bytes()
        manifest["artifacts"][name]["bytes"] = len(content)
        manifest["artifacts"][name]["sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path.write_bytes(_canonical(manifest))
    sealed_names = sorted(payload_names | {"manifest.json"})
    checksums = "".join(
        f"{hashlib.sha256((path / name).read_bytes()).hexdigest()}  {name}\n"
        for name in sealed_names
    )
    (path / "checksums.sha256").write_text(checksums)


def test_new_bundle_passes_independent_verification(tmp_path) -> None:
    result = verify_bundle(_build(tmp_path))
    assert result.valid is True
    assert result.errors == ()
    assert result.checked_files == 9


def test_identical_inputs_produce_byte_identical_bundles(tmp_path) -> None:
    first = _build(tmp_path, "first")
    second = _build(tmp_path, "second")
    assert _files(first) == _files(second)


def test_altered_artifact_fails_verification(tmp_path) -> None:
    path = _build(tmp_path)
    with (path / "report.md").open("ab") as handle:
        handle.write(b"altered\n")
    result = verify_bundle(path)
    assert result.valid is False
    assert "checksum_mismatch:report.md" in result.errors


def test_missing_file_fails_verification(tmp_path) -> None:
    path = _build(tmp_path)
    (path / "state.json").unlink()
    result = verify_bundle(path)
    assert result.errors == ("missing_file:state.json",)


def test_unexpected_file_fails_verification(tmp_path) -> None:
    path = _build(tmp_path)
    (path / "unsealed.txt").write_text("not part of the contract")
    result = verify_bundle(path)
    assert result.errors == ("unexpected_file:unsealed.txt",)


def test_existing_target_is_rejected(tmp_path) -> None:
    path = _build(tmp_path)
    with pytest.raises(BundleExistsError):
        build_campaign_bundle(
            CampaignScenario.MISSING,
            path,
            bundle_id="replacement",
            created_at=CREATED_AT,
        )


def test_semantic_mismatch_fails_even_after_hashes_are_resealed(tmp_path) -> None:
    path = _build(tmp_path)
    run_path = path / "run.json"
    run = json.loads(run_path.read_text())
    run["event_count"] += 1
    run_path.write_bytes(_canonical(run))
    _reseal(path)
    result = verify_bundle(path)
    assert result.valid is False
    assert "run_event_count_mismatch" in result.errors


def test_finding_references_resolve_to_sealed_ledger_rows(tmp_path) -> None:
    path = _build(tmp_path)
    result = verify_bundle(path)
    findings = [
        json.loads(line)
        for line in (path / "quality_findings.jsonl").read_text().splitlines()
    ]
    assert result.valid is True
    assert findings[0]["event_ids"]
    assert findings[0]["ledger_ordinals"]


def test_report_does_not_claim_preverified_validity(tmp_path) -> None:
    report = (_build(tmp_path) / "report.md").read_text()
    assert "Bundle sealed; independent verification required." in report
    assert "sensor failure is not inferred" not in report


def test_cli_build_and_verify(tmp_path, capsys) -> None:
    path = tmp_path / "cli-bundle"
    assert (
        main(
            [
                "build-demo",
                "missing",
                "--output",
                str(path),
                "--bundle-id",
                "cli-demo-001",
                "--created-at",
                "2026-01-02T03:04:05Z",
            ]
        )
        == 0
    )
    build_output = json.loads(capsys.readouterr().out)
    assert build_output["status"] == "sealed"
    assert main(["verify", str(path)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is True

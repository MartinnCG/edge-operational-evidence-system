"""Process-level abrupt restart and recovery proof tests."""

import json
from pathlib import Path

import pytest

from edge_evidence.bundle import verify_bundle
from edge_evidence.recovery import CRASH_EXIT_CODE, main, run_recovery_campaign


def test_abrupt_restart_redelivery_converges_and_verifies(tmp_path: Path) -> None:
    result = run_recovery_campaign(
        tmp_path / "campaign", seed=2026, count=8, crash_after=4
    )
    assert result.child_exit_code == CRASH_EXIT_CODE
    assert result.committed_before_restart == 4
    assert result.event_count == 8
    assert result.recovered_state_sha256 == result.reference_state_sha256
    assert result.runtime_metrics == {
        "accepted": 4,
        "disconnects": 1,
        "duplicates": 4,
        "messages_received": 8,
        "reconnects": 1,
        "rejected": 0,
    }
    assert result.bundle_valid is True
    assert verify_bundle(result.bundle_path).valid is True


def test_recovery_workspace_is_write_once(tmp_path: Path) -> None:
    workspace = tmp_path / "existing"
    workspace.mkdir()
    with pytest.raises(FileExistsError):
        run_recovery_campaign(workspace)


def test_identical_recovery_inputs_produce_identical_bundles(tmp_path: Path) -> None:
    first = run_recovery_campaign(tmp_path / "first")
    second = run_recovery_campaign(tmp_path / "second")
    first_files = {
        item.name: item.read_bytes() for item in first.bundle_path.iterdir()
    }
    second_files = {
        item.name: item.read_bytes() for item in second.bundle_path.iterdir()
    }
    assert first.recovered_state_sha256 == second.recovered_state_sha256
    assert first_files == second_files


@pytest.mark.parametrize(
    ("count", "crash_after"), [(1, 0), (4, 0), (4, 4), (4, 5)]
)
def test_invalid_campaign_boundaries_are_rejected(
    tmp_path: Path, count: int, crash_after: int
) -> None:
    with pytest.raises(ValueError):
        run_recovery_campaign(
            tmp_path / f"bad-{count}-{crash_after}",
            count=count,
            crash_after=crash_after,
        )


def test_recovery_cli_emits_machine_readable_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "run",
            "--workspace",
            str(tmp_path / "cli-campaign"),
            "--count",
            "6",
            "--crash-after",
            "3",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["bundle_valid"] is True
    assert output["committed_before_restart"] == 3
    assert output["runtime_metrics"]["duplicates"] == 3

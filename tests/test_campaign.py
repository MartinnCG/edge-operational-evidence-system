"""End-to-end synthetic failure campaign evidence for M4."""

import pytest

from edge_evidence.campaign import CampaignScenario, run_campaign


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    [
        (CampaignScenario.DELAYED, "delayed_arrival"),
        (CampaignScenario.DUPLICATE, "duplicate_event_id"),
        (CampaignScenario.REORDERED, "source_sequence_regression"),
        (CampaignScenario.MALFORMED, "invalid_event"),
        (CampaignScenario.MISSING, "source_sequence_gap"),
        (CampaignScenario.STALE, "stale_source"),
        (CampaignScenario.FROZEN, "repeated_payload_run"),
    ],
)
def test_fault_campaign_detects_expected_code(
    scenario: CampaignScenario, expected_code: str
) -> None:
    assert expected_code in run_campaign(scenario).detected_codes


def test_baseline_campaign_has_no_findings() -> None:
    result = run_campaign(CampaignScenario.BASELINE)
    assert result.detected_codes == ()
    assert result.quality_findings == ()
    assert result.boundary_findings == ()


def test_campaign_is_byte_identical_and_digest_stable() -> None:
    first = run_campaign(CampaignScenario.FROZEN, seed=91)
    second = run_campaign(CampaignScenario.FROZEN, seed=91)
    assert first.canonical_json() == second.canonical_json()
    assert first.sha256_digest() == second.sha256_digest()


def test_boundary_outcomes_remain_explicit() -> None:
    duplicate = run_campaign(CampaignScenario.DUPLICATE)
    malformed = run_campaign(CampaignScenario.MALFORMED)
    assert duplicate.duplicate_count == 1
    assert duplicate.boundary_findings[0]["classifier_version"] == "1.0"
    assert malformed.invalid_count == 1

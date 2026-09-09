import uuid
from pathlib import Path

from vendor_orchestrator.agent.loop import packet_is_incomplete, select_vendors
from vendor_orchestrator.agent.types import Decision
from vendor_orchestrator.eval_harness import (
    format_scorecard,
    load_fixtures,
    precision_by_label,
)
from vendor_orchestrator.orchestration.fanout import is_retryable
from vendor_orchestrator.orchestration.idempotency import build_idempotency_key


def test_idempotency_key_is_stable() -> None:
    case_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
    first = build_idempotency_key(case_id, "alpha")
    second = build_idempotency_key(case_id, "alpha")
    assert first == second
    assert (
        first == "case:00000000-0000-0000-0000-000000000123:vendor:alpha:purpose:check"
    )


def test_retry_classifier_retries_transient_only() -> None:
    assert is_retryable(503, None) is True
    assert is_retryable(429, None) is True
    assert is_retryable(408, None) is True
    assert is_retryable(500, None) is True
    assert is_retryable(400, None) is False
    assert is_retryable(404, None) is False
    assert is_retryable(200, None) is False
    assert is_retryable(None, TimeoutError("slow")) is True
    assert is_retryable(None, ValueError("no")) is False


def test_select_vendors_does_not_blindly_fan_out() -> None:
    available = ["alpha", "beta"]
    assert select_vendors({}, available) == ["alpha"]
    assert select_vendors({"vendors": ["beta"]}, available) == ["beta"]
    assert select_vendors({"vendors": ["beta", "alpha"]}, available) == [
        "beta",
        "alpha",
    ]
    assert select_vendors({"vendors": ["missing"]}, available) == ["alpha"]


def test_packet_incomplete_only_when_explicitly_false() -> None:
    assert packet_is_incomplete({"packet_complete": False}) is True
    assert packet_is_incomplete({"packet_complete": True}) is False
    assert packet_is_incomplete({}) is False


def test_eval_fixtures_load_and_are_labeled() -> None:
    fixtures = load_fixtures()
    assert len(fixtures) >= 3
    labels = {row.expected_decision for row in fixtures}
    assert labels == {Decision.ESCALATE.value, Decision.AUTO_RESOLVE.value}
    for row in fixtures:
        assert row.id
        assert row.subject
        assert isinstance(row.payload, dict)
        assert "label only" in row.notes.lower() or "mock fixture" in row.notes.lower()


def test_precision_on_toy_predictions_not_production() -> None:
    y_true = ["escalate", "escalate", "auto_resolve"]
    y_pred = ["escalate", "auto_resolve", "auto_resolve"]
    reports = precision_by_label(y_true, y_pred)  # type: ignore[arg-type]
    assert reports["escalate"].precision == 1.0
    assert reports["auto_resolve"].precision == 0.5
    assert reports["escalate"].recall == 0.5
    assert reports["auto_resolve"].recall == 1.0


def test_scorecard_without_predictions_has_no_invented_metric() -> None:
    fixtures = load_fixtures()
    text = format_scorecard(fixtures, reports=None)
    assert "not implemented" in text
    assert "not production" in text.lower()
    assert "1.00" not in text
    assert "100%" not in text


def test_fixture_file_lives_in_repo() -> None:
    path = Path("evals/fixtures/labeled_cases.jsonl")
    assert path.is_file()

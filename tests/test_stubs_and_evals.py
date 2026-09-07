import uuid
from pathlib import Path

import pytest

from vendor_orchestrator.agent.loop import decide_case
from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.agent.types import Decision
from vendor_orchestrator.eval_harness import (
    format_scorecard,
    load_fixtures,
    precision_by_label,
)
from vendor_orchestrator.models import Case
from vendor_orchestrator.orchestration.fanout import fan_out_vendors, is_retryable
from vendor_orchestrator.orchestration.idempotency import build_idempotency_key


def test_idempotency_key_is_stable() -> None:
    case_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
    first = build_idempotency_key(case_id, "alpha")
    second = build_idempotency_key(case_id, "alpha")
    assert first == second
    assert (
        first == "case:00000000-0000-0000-0000-000000000123:vendor:alpha:purpose:check"
    )


async def test_agent_loop_is_explicitly_unimplemented() -> None:
    case = Case(subject="stub", payload={})
    case.id = uuid.uuid4()

    class _DeadSession:
        pass

    tools = Toolbelt(_DeadSession(), case)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="YOU IMPLEMENT"):
        await decide_case(case, tools)


async def test_fanout_is_explicitly_unimplemented() -> None:
    with pytest.raises(NotImplementedError, match="YOU IMPLEMENT"):
        await fan_out_vendors(
            session=None,  # type: ignore[arg-type]
            case_id=uuid.uuid4(),
            vendor_names=["alpha"],
            payload={},
        )


def test_retry_classifier_is_explicitly_unimplemented() -> None:
    with pytest.raises(NotImplementedError, match="YOU IMPLEMENT"):
        is_retryable(503, None)


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

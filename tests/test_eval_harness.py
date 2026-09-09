import subprocess
import sys

from vendor_orchestrator.eval_harness import (
    accuracy,
    format_scorecard,
    load_fixtures,
    precision_by_label,
    run_fixture_decisions,
)


def test_eval_harness_cli_prints_live_fixture_scores() -> None:
    # Subprocess so asyncio.run in the CLI does not close pytest's event loop.
    completed = subprocess.run(
        [sys.executable, "-m", "vendor_orchestrator.eval_harness"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    text = completed.stdout
    assert "not implemented" not in text
    assert "not production" in text.lower()
    assert "tp=" in text
    assert "fx-001" in text
    assert "fx-002" in text
    assert "fx-003" in text
    assert "agent loop not implemented" not in text


async def test_fixture_run_metrics_are_computed_not_hardcoded() -> None:
    fixtures = load_fixtures()
    runs = await run_fixture_decisions(fixtures)
    y_true = [row.expected_decision for row in fixtures]
    y_pred = [row.predicted for row in runs]
    reports = precision_by_label(y_true, y_pred)
    acc = accuracy(y_true, y_pred)
    text = format_scorecard(fixtures, reports, runs=runs, overall_accuracy=acc)

    assert acc is not None
    assert f"{acc:.3f}" in text
    for label in ("escalate", "auto_resolve"):
        report = reports[label]
        assert report.precision is not None
        assert f"{report.precision:.3f}" in text
        labeled = sum(1 for row in fixtures if row.expected_decision == label)
        assert report.support == labeled

    assert {row.fixture.id for row in runs} == {row.id for row in fixtures}
    assert all(row.reason for row in runs)

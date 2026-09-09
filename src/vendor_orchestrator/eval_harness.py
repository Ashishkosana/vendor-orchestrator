"""Eval harness: labeled fixtures + precision on escalate vs auto-resolve.

Scores are computed only by running ``decide_case`` against fixtures.
This module never invents production metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import async_sessionmaker

from vendor_orchestrator.agent.loop import decide_case
from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.db import SQLITE_MEMORY_URL, make_async_engine
from vendor_orchestrator.models import Base, Case, CaseStatus

DecisionLabel = Literal["escalate", "auto_resolve"]
VALID_LABELS: frozenset[str] = frozenset({"escalate", "auto_resolve"})


@dataclass(frozen=True)
class LabeledCase:
    id: str
    subject: str
    payload: dict[str, Any]
    expected_decision: DecisionLabel
    notes: str = ""


@dataclass(frozen=True)
class FixtureRun:
    fixture: LabeledCase
    predicted: DecisionLabel
    reason: str
    vendors_used: tuple[str, ...]


@dataclass(frozen=True)
class PrecisionReport:
    label: DecisionLabel
    true_positives: int
    false_positives: int
    support: int

    @property
    def precision(self) -> float | None:
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return None
        return self.true_positives / denom

    @property
    def recall(self) -> float | None:
        if self.support == 0:
            return None
        return self.true_positives / self.support


def default_fixtures_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "evals"
        / "fixtures"
        / "labeled_cases.jsonl"
    )


def load_fixtures(path: Path | None = None) -> list[LabeledCase]:
    fixture_path = path or default_fixtures_path()
    if not fixture_path.is_file():
        raise FileNotFoundError(f"Eval fixtures not found: {fixture_path}")

    cases: list[LabeledCase] = []
    for line_no, raw in enumerate(
        fixture_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        data = json.loads(line)
        label = data.get("expected_decision")
        if label not in VALID_LABELS:
            raise ValueError(
                f"{fixture_path}:{line_no} bad expected_decision={label!r}"
            )
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"{fixture_path}:{line_no} payload must be an object")
        cases.append(
            LabeledCase(
                id=str(data["id"]),
                subject=str(data["subject"]),
                payload=payload,
                expected_decision=label,
                notes=str(data.get("notes") or ""),
            )
        )
    return cases


def precision_by_label(
    y_true: Sequence[DecisionLabel],
    y_pred: Sequence[DecisionLabel],
) -> dict[DecisionLabel, PrecisionReport]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")

    reports: dict[DecisionLabel, PrecisionReport] = {}
    for label in ("escalate", "auto_resolve"):
        tp = sum(
            1 for t, p in zip(y_true, y_pred, strict=True) if p == label and t == label
        )
        fp = sum(
            1 for t, p in zip(y_true, y_pred, strict=True) if p == label and t != label
        )
        support = sum(1 for t in y_true if t == label)
        reports[label] = PrecisionReport(
            label=label, true_positives=tp, false_positives=fp, support=support
        )
    return reports


def accuracy(
    y_true: Sequence[DecisionLabel], y_pred: Sequence[DecisionLabel]
) -> float | None:
    if not y_true:
        return None
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    hits = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)
    return hits / len(y_true)


def fixture_label_counts(cases: Iterable[LabeledCase]) -> dict[str, int]:
    counts = {"escalate": 0, "auto_resolve": 0}
    for case in cases:
        counts[case.expected_decision] += 1
    return counts


def format_scorecard(
    cases: Sequence[LabeledCase],
    reports: dict[DecisionLabel, PrecisionReport] | None,
    *,
    runs: Sequence[FixtureRun] | None = None,
    overall_accuracy: float | None = None,
) -> str:
    counts = fixture_label_counts(cases)
    lines = [
        "Eval scorecard (mock fixtures only — not production traffic)",
        f"  fixtures: {len(cases)}  "
        f"(escalate={counts['escalate']}, auto_resolve={counts['auto_resolve']})",
    ]
    if reports is None:
        lines.append("  precision(escalate):     —   agent loop not implemented")
        lines.append("  precision(auto_resolve): —   agent loop not implemented")
        lines.append("  No live model score is reported. Do not invent one.")
        return "\n".join(lines)

    if overall_accuracy is not None:
        lines.append(f"  accuracy: {overall_accuracy:.3f}  (from this fixture run)")

    for label in ("escalate", "auto_resolve"):
        report = reports[label]
        prec = "—" if report.precision is None else f"{report.precision:.3f}"
        rec = "—" if report.recall is None else f"{report.recall:.3f}"
        lines.append(
            f"  precision({label}): {prec}  recall({label}): {rec}  "
            f"(tp={report.true_positives}, fp={report.false_positives}, "
            f"support={report.support})"
        )
    lines.append("  Source: labeled eval fixtures, not production vendor traffic.")
    if runs:
        lines.append("  Per-fixture (predicted vs human label):")
        for run in runs:
            mark = "ok" if run.predicted == run.fixture.expected_decision else "miss"
            vendors = ",".join(run.vendors_used) if run.vendors_used else "none"
            lines.append(
                f"    {run.fixture.id}  expected={run.fixture.expected_decision}  "
                f"predicted={run.predicted}  vendors={vendors}  [{mark}]"
            )
            lines.append(f"      reason: {run.reason}")
    return "\n".join(lines)


async def run_fixture_decisions(cases: Sequence[LabeledCase]) -> list[FixtureRun]:
    """Run ``decide_case`` on each fixture using an in-memory SQLite session."""
    engine = make_async_engine(SQLITE_MEMORY_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    runs: list[FixtureRun] = []
    try:
        for fixture in cases:
            async with factory() as session:
                case = Case(
                    subject=fixture.subject,
                    payload=dict(fixture.payload),
                    status=CaseStatus.OPEN,
                )
                session.add(case)
                await session.flush()
                tools = Toolbelt(session, case)
                decision = await decide_case(case, tools)
                predicted = decision.decision.value
                if predicted not in VALID_LABELS:
                    raise RuntimeError(f"unexpected decision value: {predicted!r}")
                runs.append(
                    FixtureRun(
                        fixture=fixture,
                        predicted=predicted,  # type: ignore[arg-type]
                        reason=decision.reason,
                        vendors_used=decision.vendors_used,
                    )
                )
                await session.commit()
    finally:
        await engine.dispose()
    return runs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run mock-fixture eval scorecard")
    parser.add_argument("--fixtures", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    cases = load_fixtures(args.fixtures)
    runs = asyncio.run(run_fixture_decisions(cases))
    y_true = [row.expected_decision for row in cases]
    y_pred = [row.predicted for row in runs]
    reports = precision_by_label(y_true, y_pred)
    print(
        format_scorecard(
            cases,
            reports,
            runs=runs,
            overall_accuracy=accuracy(y_true, y_pred),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

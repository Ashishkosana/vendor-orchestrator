import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.agent.loop import decide_case
from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.agent.types import Decision
from vendor_orchestrator.models import Case


async def _case(
    session: AsyncSession, payload: dict[str, object], subject: str = "t"
) -> Case:
    case = Case(subject=subject, payload=payload)
    session.add(case)
    await session.flush()
    return case


async def test_decide_case_auto_resolves_clear_complete_packet(
    session: AsyncSession,
) -> None:
    case = await _case(
        session,
        {"scenario": "happy", "packet_complete": True},
        subject="Complete intake packet",
    )
    decision = await decide_case(case, Toolbelt(session, case))
    assert decision.decision is Decision.AUTO_RESOLVE
    assert decision.vendors_used == ("alpha",)
    assert "clear" in decision.reason


async def test_decide_case_escalates_on_review_signal(session: AsyncSession) -> None:
    case = await _case(
        session,
        {"scenario": "review", "packet_complete": True},
        subject="Intake with review signal",
    )
    decision = await decide_case(case, Toolbelt(session, case))
    assert decision.decision is Decision.ESCALATE
    assert decision.vendors_used == ("alpha",)
    assert "review" in decision.reason


async def test_decide_case_escalates_incomplete_packet_without_vendors(
    session: AsyncSession,
) -> None:
    case = await _case(
        session,
        {"scenario": "happy", "packet_complete": False},
        subject="Sparse intake",
    )
    decision = await decide_case(case, Toolbelt(session, case))
    assert decision.decision is Decision.ESCALATE
    assert decision.vendors_used == ()
    assert "packet_complete" in decision.reason


async def test_decide_case_can_fan_out_explicit_vendor_list(
    session: AsyncSession,
) -> None:
    case = await _case(
        session,
        {"scenario": "happy", "packet_complete": True, "vendors": ["alpha", "beta"]},
    )
    decision = await decide_case(case, Toolbelt(session, case))
    assert decision.decision is Decision.AUTO_RESOLVE
    assert decision.vendors_used == ("alpha", "beta")


async def test_toolbelt_rejects_unknown_vendor(session: AsyncSession) -> None:
    case = await _case(session, {"scenario": "happy"})
    tools = Toolbelt(session, case)
    try:
        await tools.call_vendor("not-registered")
    except KeyError as exc:
        assert "not-registered" in str(exc)
    else:
        raise AssertionError("expected KeyError")


async def test_decide_case_accepts_case_id(session: AsyncSession) -> None:
    case = await _case(session, {"scenario": "happy", "packet_complete": True})
    assert isinstance(case.id, uuid.UUID)
    decision = await decide_case(case, Toolbelt(session, case))
    assert decision.decision in {Decision.ESCALATE, Decision.AUTO_RESOLVE}

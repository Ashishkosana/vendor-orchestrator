from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.models import Case, VendorCall, VendorCallStatus
from vendor_orchestrator.orchestration.fanout import fan_out_vendors
from vendor_orchestrator.orchestration.idempotency import build_idempotency_key
from vendor_orchestrator.vendors.mock_app import INVOKE_COUNTS


async def _call_count(session: AsyncSession, case_id: object) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(VendorCall)
        .where(VendorCall.case_id == case_id)
    )
    assert count is not None
    return int(count)


async def _case(session: AsyncSession, payload: dict[str, object]) -> Case:
    case = Case(subject="fan-out case", payload=payload)
    session.add(case)
    await session.flush()
    return case


async def test_fanout_calls_alpha_and_beta_concurrently(
    session: AsyncSession,
) -> None:
    case = await _case(session, {"scenario": "happy"})
    results = await fan_out_vendors(
        session,
        case.id,
        ["alpha", "beta", "alpha"],
        dict(case.payload),
        backoff_seconds=(0.0,),
    )
    assert [row.vendor_name for row in results] == ["alpha", "beta"]
    assert all(row.ok for row in results)
    assert all(row.body["signal"] == "clear" for row in results)

    assert await _call_count(session, case.id) == 2
    assert INVOKE_COUNTS["alpha"] == 1
    assert INVOKE_COUNTS["beta"] == 1


async def test_fanout_reuses_successful_idempotency_key(
    session: AsyncSession,
) -> None:
    case = await _case(session, {"scenario": "happy"})
    first = await fan_out_vendors(
        session, case.id, ["alpha"], dict(case.payload), backoff_seconds=(0.0,)
    )
    second = await fan_out_vendors(
        session, case.id, ["alpha"], dict(case.payload), backoff_seconds=(0.0,)
    )
    assert first[0].ok and second[0].ok
    assert first[0].body["signal"] == second[0].body["signal"] == "clear"
    assert INVOKE_COUNTS["alpha"] == 1

    rows = (
        (await session.execute(select(VendorCall).where(VendorCall.case_id == case.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].idempotency_key == build_idempotency_key(case.id, "alpha")
    assert rows[0].status == VendorCallStatus.SUCCESS


async def test_fanout_retries_transient_then_succeeds(
    session: AsyncSession,
) -> None:
    case = await _case(session, {"scenario": "transient"})
    results = await fan_out_vendors(
        session,
        case.id,
        ["alpha"],
        dict(case.payload),
        max_attempts=3,
        backoff_seconds=(0.0, 0.0, 0.0),
    )
    assert results[0].ok
    assert results[0].body["signal"] == "clear"

    rows = (
        (
            await session.execute(
                select(VendorCall)
                .where(VendorCall.case_id == case.id)
                .order_by(VendorCall.attempt)
            )
        )
        .scalars()
        .all()
    )
    assert [row.attempt for row in rows] == [1, 2, 3]
    assert [row.status for row in rows] == [
        VendorCallStatus.FAILED,
        VendorCallStatus.FAILED,
        VendorCallStatus.SUCCESS,
    ]
    assert all(row.idempotency_key == rows[0].idempotency_key for row in rows)
    assert INVOKE_COUNTS["alpha"] == 3


async def test_fanout_does_not_retry_client_error(
    session: AsyncSession,
) -> None:
    case = await _case(session, {"scenario": "client_error"})
    results = await fan_out_vendors(
        session,
        case.id,
        ["alpha"],
        dict(case.payload),
        max_attempts=3,
        backoff_seconds=(0.0, 0.0, 0.0),
    )
    assert results[0].ok is False
    assert results[0].http_status == 400

    assert await _call_count(session, case.id) == 1
    assert INVOKE_COUNTS["alpha"] == 1


async def test_fanout_unknown_vendor_is_terminal(session: AsyncSession) -> None:
    case = await _case(session, {"scenario": "happy"})
    results = await fan_out_vendors(
        session,
        case.id,
        ["not-a-vendor"],
        dict(case.payload),
        max_attempts=3,
        backoff_seconds=(0.0,),
    )
    assert len(results) == 1
    assert results[0].ok is False
    assert await _call_count(session, case.id) == 1

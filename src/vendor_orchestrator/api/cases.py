from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vendor_orchestrator.agent.loop import decide_case
from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.db import SessionDep
from vendor_orchestrator.models import Case, CaseStatus
from vendor_orchestrator.orchestration.runner import run_milestone1
from vendor_orchestrator.schemas import CaseCreate, CaseRead

router = APIRouter(prefix="/v1/cases", tags=["cases"])


async def _get_case_or_404(session: AsyncSession, case_id: uuid.UUID) -> Case:
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
        )
    return case


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(body: CaseCreate, session: SessionDep) -> Case:
    case = Case(
        subject=body.subject,
        payload=body.payload,
        status=CaseStatus.OPEN,
    )
    session.add(case)
    await session.flush()
    await run_milestone1(session, case)
    await session.commit()
    await session.refresh(case)
    return case


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(case_id: uuid.UUID, session: SessionDep) -> Case:
    case = await _get_case_or_404(session, case_id)
    return case


@router.post("/{case_id}/run-agent", response_model=CaseRead)
async def run_agent(case_id: uuid.UUID, session: SessionDep) -> Case:
    """Apply the agent loop and persist escalate vs auto-resolve."""
    case = await _get_case_or_404(session, case_id)
    tools = Toolbelt(session, case)
    try:
        decision = await decide_case(case, tools)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc

    case.decision = decision.decision.value
    case.decision_reason = decision.reason
    case.status = (
        CaseStatus.ESCALATED
        if decision.decision.value == "escalate"
        else CaseStatus.AUTO_RESOLVED
    )
    await session.commit()
    await session.refresh(case)
    return case

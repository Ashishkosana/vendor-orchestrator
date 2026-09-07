"""Agent decision / tool-use loop.

THIS FILE IS INTENTIONALLY UNFINISHED.

Ashish owns this module. A finished-looking policy here would be
indefensible in an interview. Implement the loop yourself, then wire it
to ``POST /v1/cases/{id}/run-agent`` and the eval harness.
"""

from __future__ import annotations

from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.agent.types import AgentDecision
from vendor_orchestrator.models import Case


async def decide_case(case: Case, tools: Toolbelt) -> AgentDecision:
    """Choose vendors, observe results, return escalate | auto_resolve.

    YOU IMPLEMENT — suggested steps (adapt, do not cargo-cult):

    1. Read ``case.payload`` (and ``case.subject``). Decide whether any
       vendor evidence is needed. Do **not** blindly call every vendor.
    2. Select a subset of ``tools.available_vendors()`` and call them via
       ``await tools.call_vendor(name)``. Later, switch this to fan-out
       so retries/idempotency stay out of this function.
    3. Inspect persisted ``VendorCall.response_payload`` values as evidence.
    4. Return ``AgentDecision`` with:
         - ``decision``: ``Decision.ESCALATE`` or ``Decision.AUTO_RESOLVE``
         - ``reason``: short, inspectable, written for evals (not marketing)
         - ``vendors_used``: the names you actually called
    5. Keep the policy honest: mock vendors + labeled fixtures, not
       "production compliance / KYB / AML / sanctions" claims.

    Interview framing that matches this repo: orchestration + case state +
    evals. The interesting part is *your* selection and decision rule.
    """
    # YOU IMPLEMENT: agent decision / tool-use loop
    raise NotImplementedError(
        "YOU IMPLEMENT: agent decision/tool-use loop "
        f"(case_id={case.id}, available_vendors={tools.available_vendors()})"
    )

"""Agent decision / tool-use loop.

Policy is intentionally small and inspectable: incomplete intake escalates
without spending vendors; otherwise consult a subset of mock vendors and
escalate unless every consulted vendor returns ``signal=clear``.

This is not a KYB/AML/sanctions product. Vendors are mocks. The rule exists
so labeled fixtures can score escalate vs auto-resolve honestly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vendor_orchestrator.agent.tools import Toolbelt
from vendor_orchestrator.agent.types import AgentDecision, Decision
from vendor_orchestrator.models import Case
from vendor_orchestrator.vendors.base import VendorResult


def packet_is_incomplete(payload: dict[str, Any]) -> bool:
    """Escalate when the intake packet is explicitly incomplete.

    Missing ``packet_complete`` is treated as "complete enough to consult
    vendors" so ordinary create-case payloads still get a vendor check.
    """
    return payload.get("packet_complete") is False


def select_vendors(payload: dict[str, Any], available: Sequence[str]) -> list[str]:
    """Pick a subset of registered vendors. Do not blindly call every name.

    ``payload["vendors"]`` is an optional explicit list (eval / tests).
    Otherwise the primary mock (``alpha``) is enough evidence for this policy.
    """
    available_set = set(available)
    requested = payload.get("vendors")
    if isinstance(requested, list):
        selected = [
            name
            for name in requested
            if isinstance(name, str) and name in available_set
        ]
        if selected:
            return selected
    if "alpha" in available_set:
        return ["alpha"]
    return list(available)[:1]


def _signal(result: VendorResult) -> str | None:
    raw = (result.body or {}).get("signal")
    if raw is None:
        return None
    return str(raw)


async def decide_case(case: Case, tools: Toolbelt) -> AgentDecision:
    """Choose vendors, observe mock results, return escalate | auto_resolve."""
    payload = dict(case.payload or {})

    if packet_is_incomplete(payload):
        return AgentDecision(
            decision=Decision.ESCALATE,
            reason="packet_complete is false; escalate without additional vendor calls",
            vendors_used=(),
        )

    selected = tuple(select_vendors(payload, tools.available_vendors()))
    if not selected:
        return AgentDecision(
            decision=Decision.ESCALATE,
            reason="no registered mock vendors available to consult",
            vendors_used=(),
        )

    results = await tools.call_vendors(selected)
    for result in results:
        if not result.ok:
            return AgentDecision(
                decision=Decision.ESCALATE,
                reason=(
                    f"vendor {result.vendor_name} call failed "
                    f"(http={result.http_status})"
                ),
                vendors_used=selected,
            )
        signal = _signal(result)
        if signal != "clear":
            return AgentDecision(
                decision=Decision.ESCALATE,
                reason=(f"vendor {result.vendor_name} signal={signal!r} is not clear"),
                vendors_used=selected,
            )

    names = ", ".join(selected)
    return AgentDecision(
        decision=Decision.AUTO_RESOLVE,
        reason=f"packet complete and mock vendor(s) [{names}] returned signal=clear",
        vendors_used=selected,
    )

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    ESCALATE = "escalate"
    AUTO_RESOLVE = "auto_resolve"


@dataclass(frozen=True)
class AgentDecision:
    decision: Decision
    reason: str
    vendors_used: tuple[str, ...]

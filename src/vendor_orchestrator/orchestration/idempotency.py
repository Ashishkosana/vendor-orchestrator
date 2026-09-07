import uuid


def build_idempotency_key(
    case_id: uuid.UUID,
    vendor_name: str,
    *,
    purpose: str = "check",
) -> str:
    """Stable key so a retried vendor call can be recognized as the same attempt.

    Format is a scaffold convention, not a vendor-imposed standard. Later fan-out
    should reuse this helper rather than inventing a second scheme.
    """
    return f"case:{case_id}:vendor:{vendor_name}:purpose:{purpose}"

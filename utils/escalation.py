"""
Rule-based escalation stages and tones (source of truth for finance policy).
LLM follows these rules; it does not invent the stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

STAGE_DEFINITIONS: dict[int, dict[str, Any]] = {
    1: {
        "min_days": 1,
        "max_days": 7,
        "tone": "Warm & Friendly",
        "generate_email": True,
    },
    2: {
        "min_days": 8,
        "max_days": 14,
        "tone": "Polite but Firm",
        "generate_email": True,
    },
    3: {
        "min_days": 15,
        "max_days": 21,
        "tone": "Formal & Serious",
        "generate_email": True,
    },
    4: {
        "min_days": 22,
        "max_days": 30,
        "tone": "Stern & Urgent",
        "generate_email": True,
    },
    5: {
        "min_days": 31,
        "max_days": None,
        "tone": "Legal / Manual Review",
        "generate_email": False,
    },
}


def escalation_stage_for_days(days_overdue: int) -> int | None:
    """
    Map days overdue to escalation stage.

    Returns None when not overdue (0 days) — caller should not auto-generate.
    """
    if days_overdue <= 0:
        return None
    if 1 <= days_overdue <= 7:
        return 1
    if 8 <= days_overdue <= 14:
        return 2
    if 15 <= days_overdue <= 21:
        return 3
    if 22 <= days_overdue <= 30:
        return 4
    return 5


def tone_for_stage(stage: int) -> str:
    return str(STAGE_DEFINITIONS.get(stage, STAGE_DEFINITIONS[5])["tone"])


def should_generate_email(stage: int | None) -> bool:
    if stage is None:
        return False
    return bool(STAGE_DEFINITIONS.get(stage, {}).get("generate_email", False))


@dataclass(frozen=True)
class EscalationRow:
    escalation_stage: int | None
    tone: str
    generate_email: bool
    flagged_legal_review: bool


def classify_row(days_overdue: int) -> EscalationRow:
    stage = escalation_stage_for_days(days_overdue)
    if stage is None:
        return EscalationRow(
            escalation_stage=None,
            tone="N/A (not overdue)",
            generate_email=False,
            flagged_legal_review=False,
        )
    flagged = stage == 5
    tone = tone_for_stage(stage)
    gen = should_generate_email(stage)
    return EscalationRow(
        escalation_stage=stage,
        tone=tone,
        generate_email=gen,
        flagged_legal_review=flagged,
    )


def apply_escalation_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add escalation_stage, tone, generate_email, flagged_legal_review columns."""
    out = df.copy()
    classes = [classify_row(int(d)) for d in out["days_overdue"].tolist()]
    out["escalation_stage"] = [c.escalation_stage for c in classes]
    # Nullable integer dtype avoids float NaN in CSV/UI previews
    out["escalation_stage"] = pd.array(out["escalation_stage"], dtype="Int64")
    out["tone"] = [c.tone for c in classes]
    out["generate_email"] = [c.generate_email for c in classes]
    out["flagged_legal_review"] = [c.flagged_legal_review for c in classes]
    return out

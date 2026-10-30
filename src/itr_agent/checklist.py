"""Work out which supporting documents the user should have, and which are still missing.

Rules are deliberately conservative. A document is only marked "missing" when
the AIS gives evidence it is needed. Without an AIS, needs are "unknown" rather
than guessed.
"""

from typing import Literal

from pydantic import BaseModel

from .schemas import AISData

Status = Literal["present", "missing", "not_needed", "unknown"]


class ChecklistItem(BaseModel):
    document_type: str
    label: str
    status: Status
    reason: str


def build_checklist(ais: AISData | None, present: set[str]) -> list[ChecklistItem]:
    items = [
        ChecklistItem(
            document_type="ais",
            label="Annual Information Statement (AIS)",
            status="present" if "ais" in present else "missing",
            reason="Ground truth for income, TDS and transactions. Pre-fills most of the return.",
        ),
        ChecklistItem(
            document_type="form26as",
            label="Form 26AS (tax credit statement)",
            status="present" if "form26as" in present else "missing",
            reason="Cross-checks the TDS credited to you by every deductor.",
        ),
    ]

    if ais is None:
        unknown_reason = "Upload the AIS first, so this can be checked against it."
        items.append(
            ChecklistItem(
                document_type="form16",
                label="Form 16 (one per employer)",
                status="present" if "form16" in present else "unknown",
                reason=unknown_reason,
            )
        )
        items.append(
            ChecklistItem(
                document_type="broker_pnl",
                label="Broker tax P&L statement",
                status="present" if "broker_pnl" in present else "unknown",
                reason=unknown_reason,
            )
        )
        return items

    items.append(_form16_item(ais, present))
    items.append(_broker_item(ais, present))
    return items


def _form16_item(ais: AISData, present: set[str]) -> ChecklistItem:
    label = "Form 16 (one per employer)"
    if "form16" in present:
        return ChecklistItem(document_type="form16", label=label, status="present", reason="Uploaded.")
    if ais.salary_income:
        employers = ", ".join(sorted({e.employer_name for e in ais.salary_income}))
        return ChecklistItem(
            document_type="form16",
            label=label,
            status="missing",
            reason=f"The AIS shows salary from {employers}. Each employer issues one Form 16.",
        )
    return ChecklistItem(
        document_type="form16",
        label=label,
        status="not_needed",
        reason="The AIS shows no salary income.",
    )


def _broker_item(ais: AISData, present: set[str]) -> ChecklistItem:
    label = "Broker tax P&L statement"
    if "broker_pnl" in present:
        return ChecklistItem(document_type="broker_pnl", label=label, status="present", reason="Uploaded.")
    if ais.capital_gains_summary or ais.reported_transactions:
        return ChecklistItem(
            document_type="broker_pnl",
            label=label,
            status="missing",
            reason="The AIS reports share or fund sales. Your broker's P&L statement gives the cost and sale detail.",
        )
    return ChecklistItem(
        document_type="broker_pnl",
        label=label,
        status="not_needed",
        reason="The AIS shows no sales. If you traded anyway, upload your broker statement.",
    )

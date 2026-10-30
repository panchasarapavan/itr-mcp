"""Layer 2 validation gate: deterministic checks on AI-normalized trades.

Errors block the trades. Warnings are advisory: they are reported but do not
stop the batch, because a pre-period holding or an intraday round trip can look
suspicious and still be correct.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import AssetClass, Currency, Exchange, NormalizedTrade

EXCHANGE_CURRENCY: dict[Exchange, Currency] = {
    "NSE": "INR",
    "BSE": "INR",
    "NYSE": "USD",
    "NASDAQ": "USD",
}
FOREIGN_EXCHANGES: frozenset[Exchange] = frozenset({"NYSE", "NASDAQ"})

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class ValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning"]
    code: str
    message: str
    trade_index: int | None = None


class ValidationReport(BaseModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(issue.severity != "error" for issue in self.issues)


def infer_asset_class(exchange: Exchange) -> AssetClass | None:
    """Foreign exchanges imply FOREIGN_EQUITY. Indian exchanges cannot be inferred."""
    return "FOREIGN_EQUITY" if exchange in FOREIGN_EXCHANGES else None


def is_valid_isin(isin: str) -> bool:
    """Check the ISIN format and its Luhn check digit (ISO 6166)."""
    if not ISIN_PATTERN.fullmatch(isin):
        return False
    # Letters become two digits (A=10 ... Z=35), then Luhn runs over the whole string.
    digits = "".join(str(int(ch, 36)) for ch in isin)
    total = 0
    for position, ch in enumerate(reversed(digits)):
        value = int(ch)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def validate_trades(
    trades: Sequence[NormalizedTrade],
    today: date | None = None,
) -> ValidationReport:
    today = today or date.today()
    issues: list[ValidationIssue] = []
    for index, trade in enumerate(trades):
        issues.extend(_check_trade(index, trade, today))
    issues.extend(_check_duplicates(trades))
    issues.extend(_check_holdings(trades))
    return ValidationReport(issues=issues)


def _check_trade(index: int, trade: NormalizedTrade, today: date) -> list[ValidationIssue]:
    found: list[ValidationIssue] = []

    def add(severity: Literal["error", "warning"], code: str, message: str) -> None:
        found.append(ValidationIssue(severity=severity, code=code, message=message, trade_index=index))

    if trade.quantity <= 0:
        add("error", "non_positive_quantity", f"quantity must be greater than 0, got {trade.quantity}")
    if trade.price_per_unit <= 0:
        add("error", "non_positive_price", f"price_per_unit must be greater than 0, got {trade.price_per_unit}")
    if trade.brokerage < 0:
        add("error", "negative_charge", f"brokerage cannot be negative, got {trade.brokerage}")
    if trade.stt_paid < 0:
        add("error", "negative_charge", f"stt_paid cannot be negative, got {trade.stt_paid}")
    if trade.trade_date > today:
        add("error", "future_trade_date", f"trade_date {trade.trade_date} is after today ({today})")
    if trade.isin is not None and not is_valid_isin(trade.isin):
        add("error", "invalid_isin", f"'{trade.isin}' is not a valid ISIN (format or check digit)")

    expected_currency = EXCHANGE_CURRENCY[trade.exchange]
    if trade.currency != expected_currency:
        add(
            "error",
            "currency_exchange_mismatch",
            f"{trade.exchange} trades are in {expected_currency}, got {trade.currency}",
        )

    is_foreign = trade.exchange in FOREIGN_EXCHANGES
    if is_foreign and trade.asset_class != "FOREIGN_EQUITY":
        add(
            "error",
            "asset_class_mismatch",
            f"{trade.exchange} trades must be FOREIGN_EQUITY, got {trade.asset_class}",
        )
    if not is_foreign and trade.asset_class == "FOREIGN_EQUITY":
        add(
            "error",
            "asset_class_mismatch",
            f"FOREIGN_EQUITY requires NYSE or NASDAQ, got {trade.exchange}",
        )

    return found


def _position_key(trade: NormalizedTrade) -> str:
    # Holdings are matched across exchanges, so the same stock on NSE and BSE shares one position.
    return trade.isin or trade.symbol.upper()


def _check_duplicates(trades: Sequence[NormalizedTrade]) -> list[ValidationIssue]:
    seen: dict[tuple[object, ...], int] = {}
    issues: list[ValidationIssue] = []
    for index, trade in enumerate(trades):
        signature = (
            trade.exchange,
            trade.symbol.upper(),
            trade.trade_date,
            trade.trade_type,
            trade.quantity,
            trade.price_per_unit,
        )
        if signature in seen:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="possible_duplicate",
                    message=f"identical to trade at index {seen[signature]}; keep both only if this is a genuine second fill",
                    trade_index=index,
                )
            )
        else:
            seen[signature] = index
    return issues


def _check_holdings(trades: Sequence[NormalizedTrade]) -> list[ValidationIssue]:
    # Buys sort before sells on the same date, so an intraday round trip is not flagged.
    order = sorted(
        range(len(trades)),
        key=lambda i: (trades[i].trade_date, trades[i].trade_type == "SELL", i),
    )
    held: dict[str, Decimal] = defaultdict(Decimal)
    issues: list[ValidationIssue] = []
    for index in order:
        trade = trades[index]
        key = _position_key(trade)
        if trade.trade_type == "BUY":
            held[key] += trade.quantity
            continue
        if trade.quantity > held[key]:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="sell_exceeds_known_holding",
                    message=(
                        f"SELL of {trade.quantity} {trade.symbol} on {trade.trade_date} exceeds the "
                        f"{held[key]} held from the provided trades. Fine if the shares were bought "
                        "before these documents; otherwise a BUY is missing."
                    ),
                    trade_index=index,
                )
            )
        held[key] = max(Decimal("0"), held[key] - trade.quantity)
    return issues

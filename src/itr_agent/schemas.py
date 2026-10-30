"""Strict data contracts shared by the AI parsing layer and the deterministic engines.

The AI reads any broker file or PDF and maps it into these shapes. Models forbid
unknown fields, so a mis-spelled or invented key fails validation instead of
being silently dropped.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Exchange = Literal["NSE", "BSE", "NYSE", "NASDAQ"]
AssetClass = Literal["EQUITY", "DEBT_MF", "EQUITY_MF", "FNO", "FOREIGN_EQUITY"]
Currency = Literal["INR", "USD"]
TradeType = Literal["BUY", "SELL"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizedTrade(_Strict):
    """One executed trade, normalized from any broker P&L format."""

    symbol: str = Field(min_length=1)
    isin: str | None = None
    exchange: Exchange
    asset_class: AssetClass
    trade_type: TradeType
    trade_date: date
    quantity: Decimal
    price_per_unit: Decimal
    currency: Currency
    brokerage: Decimal = Decimal("0")
    stt_paid: Decimal = Decimal("0")
    is_delivery: bool


class SalaryEntry(_Strict):
    employer_name: str
    employer_tan: str | None = None
    amount: Decimal


class InterestEntry(_Strict):
    payer_name: str
    amount: Decimal


class DividendEntry(_Strict):
    payer_name: str
    amount: Decimal


class CGSummaryEntry(_Strict):
    description: str
    amount: Decimal


class TDSCredit(_Strict):
    deductor_tan: str
    deductor_name: str
    amount: Decimal
    section: str | None = None


class ForeignRemittance(_Strict):
    description: str
    currency: str
    amount: Decimal


class OtherIncomeEntry(_Strict):
    description: str
    amount: Decimal


class ReportedTransaction(_Strict):
    description: str
    category: str
    trade_date: date | None = None
    amount: Decimal
    isin: str | None = None


class AISData(_Strict):
    """Annual Information Statement. Treated as ground truth for pre-fill."""

    salary_income: list[SalaryEntry] = Field(default_factory=list)
    interest_income: list[InterestEntry] = Field(default_factory=list)
    dividend_income: list[DividendEntry] = Field(default_factory=list)
    capital_gains_summary: list[CGSummaryEntry] = Field(default_factory=list)
    tds_credits: list[TDSCredit] = Field(default_factory=list)
    foreign_remittances: list[ForeignRemittance] = Field(default_factory=list)
    other_income: list[OtherIncomeEntry] = Field(default_factory=list)
    reported_transactions: list[ReportedTransaction] = Field(default_factory=list)


class Form16Data(_Strict):
    """Form 16 Part A (TDS) and Part B (salary breakup and income)."""

    employer_name: str
    employer_tan: str
    employee_pan: str | None = None
    assessment_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-27"])

    gross_salary: Decimal
    perquisites: Decimal = Decimal("0")
    profits_in_lieu: Decimal = Decimal("0")
    exempt_allowances: Decimal = Decimal("0")
    standard_deduction: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    income_from_salary: Decimal
    other_income: Decimal = Decimal("0")
    chapter_via_deductions: dict[str, Decimal] = Field(default_factory=dict)
    tds_deducted: Decimal = Decimal("0")


class ConfirmedData(_Strict):
    """A value that matches across two or more sources."""

    value: Decimal | None = None
    sources: list[str]


class DataGap(_Strict):
    """Data that no document provides."""

    category: str
    description: str


class DataConflict(_Strict):
    """Same category, different values across sources."""

    category: str
    values: dict[str, Decimal]
    description: str


class Question(_Strict):
    """Asked only when no document covers the information."""

    id: str
    category: str
    text: str
    options: list[str] | None = None


class ReconciliationResult(_Strict):
    confirmed: dict[str, ConfirmedData] = Field(default_factory=dict)
    gaps: list[DataGap] = Field(default_factory=list)
    conflicts: list[DataConflict] = Field(default_factory=list)
    questions_needed: list[Question] = Field(default_factory=list)
    schedule_triggers: list[str] = Field(default_factory=list)
    confidence_scores: dict[str, float] = Field(default_factory=dict)

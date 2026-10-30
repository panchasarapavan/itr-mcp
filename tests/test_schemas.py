from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from itr_agent.schemas import AISData, Form16Data, NormalizedTrade


def trade_payload(**overrides) -> dict:
    payload = {
        "symbol": "RELIANCE",
        "isin": "INE002A01018",
        "exchange": "NSE",
        "asset_class": "EQUITY",
        "trade_type": "BUY",
        "trade_date": "2025-04-10",
        "quantity": "10",
        "price_per_unit": "1250.50",
        "currency": "INR",
        "is_delivery": True,
    }
    payload.update(overrides)
    return payload


def test_trade_coerces_strings_to_typed_values():
    trade = NormalizedTrade(**trade_payload())
    assert trade.trade_date == date(2025, 4, 10)
    assert trade.quantity == Decimal("10")
    assert trade.brokerage == Decimal("0")


def test_trade_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="extra_field"):
        NormalizedTrade(**trade_payload(extra_field="oops"))


def test_trade_rejects_unknown_exchange():
    with pytest.raises(ValidationError):
        NormalizedTrade(**trade_payload(exchange="LSE"))


def test_trade_requires_symbol():
    with pytest.raises(ValidationError):
        NormalizedTrade(**trade_payload(symbol=""))


def test_form16_assessment_year_format_enforced():
    base = {
        "employer_name": "Acme Ltd",
        "employer_tan": "BLRA12345B",
        "gross_salary": "1200000",
        "income_from_salary": "1100000",
    }
    assert Form16Data(assessment_year="2026-27", **base).assessment_year == "2026-27"
    with pytest.raises(ValidationError):
        Form16Data(assessment_year="2026", **base)


def test_ais_defaults_to_empty_lists():
    ais = AISData(assessment_year="2026-27")
    assert ais.salary_income == []
    assert ais.reported_transactions == []


def test_ais_requires_assessment_year():
    with pytest.raises(ValidationError):
        AISData()

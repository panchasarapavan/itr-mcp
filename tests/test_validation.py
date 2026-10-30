from datetime import date
from decimal import Decimal

import pytest

from itr_agent.schemas import NormalizedTrade
from itr_agent.validation import infer_asset_class, is_valid_isin, validate_trades

TODAY = date(2026, 10, 30)


def make_trade(**overrides) -> NormalizedTrade:
    fields = {
        "symbol": "RELIANCE",
        "isin": "INE002A01018",
        "exchange": "NSE",
        "asset_class": "EQUITY",
        "trade_type": "BUY",
        "trade_date": date(2025, 4, 10),
        "quantity": Decimal("10"),
        "price_per_unit": Decimal("1250.50"),
        "currency": "INR",
        "brokerage": Decimal("0"),
        "stt_paid": Decimal("12.51"),
        "is_delivery": True,
    }
    fields.update(overrides)
    return NormalizedTrade(**fields)


def codes(report, severity: str) -> list[str]:
    return [issue.code for issue in report.issues if issue.severity == severity]


def test_valid_trade_passes_cleanly():
    report = validate_trades([make_trade()], today=TODAY)
    assert report.ok
    assert report.issues == []


@pytest.mark.parametrize("isin", ["US0378331005", "INE002A01018"])
def test_valid_isin_accepted(isin):
    assert is_valid_isin(isin)


@pytest.mark.parametrize(
    "isin",
    [
        "US0378331006",  # wrong check digit
        "us0378331005",  # lowercase
        "US037833100",  # too short
        "1234567890AB",  # no country prefix
    ],
)
def test_invalid_isin_rejected(isin):
    assert not is_valid_isin(isin)


def test_invalid_isin_is_an_error():
    report = validate_trades([make_trade(isin="INE002A01019")], today=TODAY)
    assert not report.ok
    assert codes(report, "error") == ["invalid_isin"]


def test_non_positive_quantity_and_price_are_errors():
    report = validate_trades(
        [make_trade(quantity=Decimal("0"), price_per_unit=Decimal("-1"))],
        today=TODAY,
    )
    assert sorted(codes(report, "error")) == ["non_positive_price", "non_positive_quantity"]


def test_negative_charges_are_errors():
    report = validate_trades([make_trade(stt_paid=Decimal("-1"))], today=TODAY)
    assert codes(report, "error") == ["negative_charge"]


def test_future_trade_date_is_error():
    report = validate_trades([make_trade(trade_date=date(2026, 11, 1))], today=TODAY)
    assert codes(report, "error") == ["future_trade_date"]


def test_nse_trade_in_usd_is_currency_mismatch():
    report = validate_trades([make_trade(currency="USD")], today=TODAY)
    assert codes(report, "error") == ["currency_exchange_mismatch"]


def test_nyse_trade_must_be_foreign_equity():
    trade = make_trade(
        symbol="AAPL",
        isin="US0378331005",
        exchange="NYSE",
        asset_class="EQUITY",
        currency="USD",
    )
    report = validate_trades([trade], today=TODAY)
    assert codes(report, "error") == ["asset_class_mismatch"]


def test_foreign_equity_on_indian_exchange_is_error():
    report = validate_trades([make_trade(asset_class="FOREIGN_EQUITY")], today=TODAY)
    assert codes(report, "error") == ["asset_class_mismatch"]


def test_infer_asset_class():
    assert infer_asset_class("NASDAQ") == "FOREIGN_EQUITY"
    assert infer_asset_class("NSE") is None


def test_sell_exceeding_holding_is_warning_not_error():
    buy = make_trade(trade_date=date(2025, 4, 1), quantity=Decimal("5"))
    sell = make_trade(trade_type="SELL", trade_date=date(2025, 5, 1), quantity=Decimal("8"))
    report = validate_trades([buy, sell], today=TODAY)
    assert report.ok
    assert codes(report, "warning") == ["sell_exceeds_known_holding"]
    assert report.issues[0].trade_index == 1


def test_sell_within_holding_is_clean():
    buy = make_trade(trade_date=date(2025, 4, 1), quantity=Decimal("10"))
    sell = make_trade(trade_type="SELL", trade_date=date(2025, 5, 1), quantity=Decimal("10"))
    assert validate_trades([buy, sell], today=TODAY).issues == []


def test_same_day_buy_then_sell_is_not_flagged_regardless_of_input_order():
    buy = make_trade(trade_date=date(2025, 4, 1), quantity=Decimal("3"))
    sell = make_trade(trade_type="SELL", trade_date=date(2025, 4, 1), quantity=Decimal("3"))
    assert validate_trades([sell, buy], today=TODAY).issues == []


def test_holdings_match_across_exchanges_by_isin():
    buy_nse = make_trade(trade_date=date(2025, 4, 1), quantity=Decimal("10"))
    sell_bse = make_trade(
        trade_type="SELL",
        trade_date=date(2025, 5, 1),
        quantity=Decimal("10"),
        exchange="BSE",
    )
    assert validate_trades([buy_nse, sell_bse], today=TODAY).issues == []


def test_identical_trades_are_flagged_as_possible_duplicate():
    trade = make_trade()
    report = validate_trades([trade, trade], today=TODAY)
    assert report.ok
    assert codes(report, "warning") == ["possible_duplicate"]
    assert report.issues[0].trade_index == 1

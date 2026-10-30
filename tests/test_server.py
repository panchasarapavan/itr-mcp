import asyncio
from datetime import date
from decimal import Decimal

import pytest

from itr_agent import server
from itr_agent.schemas import AISData, InterestEntry, NormalizedTrade, SalaryEntry, TDSCredit

AY = "2026-27"

EXPECTED_TOOLS = {
    "ingest_ais",
    "show_ais",
    "get_document_checklist",
    "ingest_26as",
    "ingest_form16",
    "ingest_trades",
    "reconcile",
    "compute_capital_gains",
    "compute_tax",
    "compute_deductions",
    "detect_schedules",
    "convert_currency",
    "validate_itr",
    "generate_itr_json",
    "get_tax_rules",
    "get_download_guide",
}


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ITR_AGENT_HOME", str(tmp_path))
    return tmp_path


def valid_trade(**overrides) -> NormalizedTrade:
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
        "is_delivery": True,
    }
    fields.update(overrides)
    return NormalizedTrade(**fields)


def test_all_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_later_phase_tools_report_not_implemented():
    result = server.reconcile()
    assert result == {"status": "not_implemented", "tool": "reconcile", "planned_for": "Phase 2"}


def test_show_ais_before_upload_asks_for_it(home):
    result = server.show_ais(assessment_year=AY)
    assert result["status"] == "missing"
    assert AY in result["message"]


def test_full_flow_ais_then_checklist_then_trades(home):
    ais = AISData(
        assessment_year=AY,
        salary_income=[SalaryEntry(employer_name="Acme Ltd", employer_tan="BLRA12345B", amount=Decimal("1200000"))],
        interest_income=[InterestEntry(payer_name="HDFC Bank", amount=Decimal("8500"))],
        tds_credits=[
            TDSCredit(deductor_tan="BLRA12345B", deductor_name="Acme Ltd", amount=Decimal("90000"), section="192")
        ],
    )

    stored = server.ingest_ais(ais=ais)
    assert stored["status"] == "stored"
    assert stored["counts"]["salary_income"] == 1

    shown = server.show_ais(assessment_year=AY)
    assert shown["status"] == "ok"
    assert "Acme Ltd" in shown["markdown"]
    assert "Total TDS" in shown["markdown"]

    checklist = server.get_document_checklist(assessment_year=AY)
    assert checklist["missing"] == ["form26as", "form16"]
    assert checklist["all_required_present"] is False
    form16 = next(item for item in checklist["items"] if item["document_type"] == "form16")
    assert form16["status"] == "missing"
    assert "Acme Ltd" in form16["reason"]
    assert "Form 16" in form16["guide_markdown"]

    trades_result = server.ingest_trades(assessment_year=AY, source="Zerodha", trades=[valid_trade()])
    assert trades_result["status"] == "accepted"
    assert trades_result["source"] == "zerodha"

    checklist = server.get_document_checklist(assessment_year=AY)
    broker = next(item for item in checklist["items"] if item["document_type"] == "broker_pnl")
    assert broker["status"] == "present"  # uploaded, even though the AIS shows no sales


def test_ingest_trades_rejects_batch_and_stores_nothing(home):
    bad = valid_trade(isin="INE002A01019")  # bad ISIN check digit
    result = server.ingest_trades(assessment_year=AY, source="zerodha", trades=[bad])
    assert result["status"] == "rejected"
    assert [issue["code"] for issue in result["report"]["issues"]] == ["invalid_isin"]
    assert server._workspace().keys(AY, "broker_pnl") == []


def test_ingest_trades_warnings_do_not_block(home):
    buy = valid_trade(trade_date=date(2025, 4, 1), quantity=Decimal("5"))
    sell = valid_trade(trade_type="SELL", trade_date=date(2025, 5, 1), quantity=Decimal("8"))
    result = server.ingest_trades(assessment_year=AY, source="zerodha", trades=[buy, sell])
    assert result["status"] == "accepted"
    assert [issue["severity"] for issue in result["report"]["issues"]] == ["warning"]


def test_checklist_marks_broker_missing_when_ais_shows_sales(home):
    ais = AISData(
        assessment_year=AY,
        capital_gains_summary=[{"description": "Equity sales", "amount": "45000"}],
    )
    server.ingest_ais(ais=ais)
    checklist = server.get_document_checklist(assessment_year=AY)
    assert "broker_pnl" in checklist["missing"]


def test_download_guide_uses_platform_when_available():
    guide = server.get_download_guide(document_type="broker_pnl", platform="zerodha")
    assert guide["platform_specific"] is True
    assert "console.zerodha.com" in guide["guide_markdown"]


def test_download_guide_falls_back_to_generic():
    guide = server.get_download_guide(document_type="broker_pnl", platform="groww")
    assert guide["platform_specific"] is False
    assert "Tax P&L" in guide["guide_markdown"]


def test_download_guide_rejects_unknown_document_type():
    with pytest.raises(ValueError):
        server.get_download_guide(document_type="passport")

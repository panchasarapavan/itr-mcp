import asyncio
from datetime import date
from decimal import Decimal

from itr_agent import server
from itr_agent.schemas import NormalizedTrade

EXPECTED_TOOLS = {
    "ingest_ais",
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


def test_all_fourteen_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_stub_tools_report_not_implemented():
    result = server.ingest_ais(file_path="/tmp/ais.pdf")
    assert result == {"status": "not_implemented", "tool": "ingest_ais", "planned_for": "Phase 2"}


def test_ingest_trades_accepts_valid_trade():
    trade = NormalizedTrade(
        symbol="RELIANCE",
        isin="INE002A01018",
        exchange="NSE",
        asset_class="EQUITY",
        trade_type="BUY",
        trade_date=date(2025, 4, 10),
        quantity=Decimal("10"),
        price_per_unit=Decimal("1250.50"),
        currency="INR",
        is_delivery=True,
    )
    result = server.ingest_trades(trades=[trade])
    assert result["status"] == "accepted"
    assert result["trade_count"] == 1
    assert result["report"]["issues"] == []


def test_ingest_trades_rejects_batch_with_errors():
    trade = NormalizedTrade(
        symbol="RELIANCE",
        isin="INE002A01019",  # bad check digit
        exchange="NSE",
        asset_class="EQUITY",
        trade_type="BUY",
        trade_date=date(2025, 4, 10),
        quantity=Decimal("10"),
        price_per_unit=Decimal("1250.50"),
        currency="INR",
        is_delivery=True,
    )
    result = server.ingest_trades(trades=[trade])
    assert result["status"] == "rejected"
    assert [issue["code"] for issue in result["report"]["issues"]] == ["invalid_isin"]

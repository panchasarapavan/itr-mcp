from datetime import date
from decimal import Decimal

import pytest

from itr_agent.checklist import build_checklist
from itr_agent.render import format_inr, render_ais_summary
from itr_agent.schemas import AISData, ReportedTransaction, SalaryEntry, TDSCredit
from itr_agent.workspace import Workspace, make_key

AY = "2026-27"


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("0"), "₹0.00"),
        (Decimal("100"), "₹100.00"),
        (Decimal("1000"), "₹1,000.00"),
        (Decimal("1234567.5"), "₹12,34,567.50"),
        (Decimal("10000000"), "₹1,00,00,000.00"),
        (Decimal("-5000"), "-₹5,000.00"),
        (Decimal("999.999"), "₹1,000.00"),
    ],
)
def test_format_inr_uses_indian_grouping(amount, expected):
    assert format_inr(amount) == expected


def test_render_escapes_pipes_and_totals_tds():
    ais = AISData(
        assessment_year=AY,
        salary_income=[SalaryEntry(employer_name="A | B Ltd", amount=Decimal("100000"))],
        tds_credits=[
            TDSCredit(deductor_tan="X", deductor_name="One", amount=Decimal("1000")),
            TDSCredit(deductor_tan="Y", deductor_name="Two", amount=Decimal("2500")),
        ],
    )
    markdown = render_ais_summary(ais)
    assert "A \\| B Ltd" in markdown
    assert "Total TDS: **₹3,500.00**" in markdown


def test_render_omits_empty_sections_and_shows_income_total():
    ais = AISData(
        assessment_year=AY,
        salary_income=[SalaryEntry(employer_name="Acme", amount=Decimal("1000000"))],
        capital_gains_summary=[{"description": "Sales", "amount": "50000"}],
    )
    markdown = render_ais_summary(ais)
    assert "### Salary" in markdown
    assert "### Interest" not in markdown
    assert "excluding capital gains): ₹10,00,000.00**" in markdown


def test_render_reported_transactions_with_missing_date():
    ais = AISData(
        assessment_year=AY,
        reported_transactions=[
            ReportedTransaction(description="Sale", category="SALE", amount=Decimal("500"), trade_date=date(2025, 6, 1)),
            ReportedTransaction(description="Other", category="OTHER", amount=Decimal("10")),
        ],
    )
    markdown = render_ais_summary(ais)
    assert "| 2025-06-01 | Sale | SALE | ₹500.00 |" in markdown
    assert "| - | Other | OTHER | ₹10.00 |" in markdown


def test_checklist_without_ais_is_unknown_not_missing():
    items = {item.document_type: item.status for item in build_checklist(None, set())}
    assert items == {"ais": "missing", "form26as": "missing", "form16": "unknown", "broker_pnl": "unknown"}


def test_checklist_salary_requires_form16_until_uploaded():
    ais = AISData(assessment_year=AY, salary_income=[SalaryEntry(employer_name="Acme", amount=Decimal("1"))])
    statuses = {item.document_type: item.status for item in build_checklist(ais, set())}
    assert statuses["form16"] == "missing"
    statuses = {item.document_type: item.status for item in build_checklist(ais, {"form16", "ais", "form26as"})}
    assert statuses["form16"] == "present"
    assert statuses["ais"] == "present"


def test_checklist_without_salary_or_sales_needs_no_extra_documents():
    statuses = {item.document_type: item.status for item in build_checklist(AISData(assessment_year=AY), set())}
    assert statuses["form16"] == "not_needed"
    assert statuses["broker_pnl"] == "not_needed"


def test_make_key_normalizes_names():
    assert make_key("Zerodha") == "zerodha"
    assert make_key("Interactive Brokers (US)") == "interactive_brokers_us"
    assert make_key("!!!") == "default"


def test_workspace_round_trip_and_presence(tmp_path):
    workspace = Workspace(tmp_path)
    assert workspace.present_types(AY) == set()

    workspace.save(AY, "form16", make_key("BLRA12345B"), {"employer_tan": "BLRA12345B"})
    assert workspace.load(AY, "form16", "blra12345b") == {"employer_tan": "BLRA12345B"}
    assert workspace.present_types(AY) == {"form16"}


def test_workspace_rejects_bad_inputs(tmp_path):
    workspace = Workspace(tmp_path)
    with pytest.raises(ValueError):
        workspace.save("2026", "ais", "default", {})
    with pytest.raises(ValueError):
        workspace.save(AY, "passport", "default", {})
    with pytest.raises(ValueError):
        workspace.save(AY, "ais", "../escape", {})

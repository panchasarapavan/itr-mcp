"""Human-readable rendering of AIS data. Output is markdown for the AI to show the user."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from .schemas import AISData

ZERO = Decimal("0")


def format_inr(amount: Decimal) -> str:
    """Format with Indian digit grouping: 1234567.5 -> '₹12,34,567.50'."""
    rounded = abs(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, _, fraction = f"{rounded:.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{whole}.{fraction}"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _section(title: str, body: str) -> str:
    return f"### {title}\n\n{body}"


def render_ais_summary(ais: AISData) -> str:
    sections: list[str] = [f"## AIS for assessment year {ais.assessment_year}"]

    if ais.salary_income:
        sections.append(
            _section(
                "Salary",
                _table(
                    ["Employer", "TAN", "Amount"],
                    [[e.employer_name, e.employer_tan or "-", format_inr(e.amount)] for e in ais.salary_income],
                ),
            )
        )
    if ais.interest_income:
        sections.append(
            _section(
                "Interest",
                _table(["Payer", "Amount"], [[e.payer_name, format_inr(e.amount)] for e in ais.interest_income]),
            )
        )
    if ais.dividend_income:
        sections.append(
            _section(
                "Dividends",
                _table(["Payer", "Amount"], [[e.payer_name, format_inr(e.amount)] for e in ais.dividend_income]),
            )
        )
    if ais.capital_gains_summary:
        sections.append(
            _section(
                "Capital gains summary",
                _table(
                    ["Description", "Amount"],
                    [[e.description, format_inr(e.amount)] for e in ais.capital_gains_summary],
                ),
            )
        )
    if ais.tds_credits:
        total_tds = sum((e.amount for e in ais.tds_credits), ZERO)
        table = _table(
            ["Deductor", "TAN", "Section", "Amount"],
            [[e.deductor_name, e.deductor_tan, e.section or "-", format_inr(e.amount)] for e in ais.tds_credits],
        )
        sections.append(_section("TDS credits", f"{table}\n\nTotal TDS: **{format_inr(total_tds)}**"))
    if ais.foreign_remittances:
        sections.append(
            _section(
                "Foreign remittances",
                _table(
                    ["Description", "Currency", "Amount"],
                    [[e.description, e.currency, format_inr(e.amount)] for e in ais.foreign_remittances],
                ),
            )
        )
    if ais.other_income:
        sections.append(
            _section(
                "Other income",
                _table(["Description", "Amount"], [[e.description, format_inr(e.amount)] for e in ais.other_income]),
            )
        )
    if ais.reported_transactions:
        sections.append(
            _section(
                "Reported transactions",
                _table(
                    ["Date", "Description", "Category", "Amount"],
                    [
                        [
                            e.trade_date.isoformat() if e.trade_date else "-",
                            e.description,
                            e.category,
                            format_inr(e.amount),
                        ]
                        for e in ais.reported_transactions
                    ],
                ),
            )
        )

    income = (
        sum((e.amount for e in ais.salary_income), ZERO)
        + sum((e.amount for e in ais.interest_income), ZERO)
        + sum((e.amount for e in ais.dividend_income), ZERO)
        + sum((e.amount for e in ais.other_income), ZERO)
    )
    sections.append(
        "**Income from salary, interest, dividends and other sources (excluding capital gains): "
        f"{format_inr(income)}**"
    )
    return "\n\n".join(sections)

"""Download guides for supporting documents, bundled with the package.

Guide text is returned for the user to read. It is never treated as
instructions to the assistant. Step-level sanitizing and remote, hash-verified
guides are planned for Phase 4.
"""

from importlib.resources import files

GUIDE_DOCUMENT_TYPES = ("ais", "form26as", "form16", "broker_pnl")

FALLBACK_HINTS = {
    "ais": "Log in to https://www.incometax.gov.in and open the Annual Information Statement.",
    "form26as": "Log in to https://www.tdscpc.gov.in (TRACES) and download Form 26AS.",
    "form16": "Ask your employer's HR or payroll team for Form 16 (Part A and Part B).",
    "broker_pnl": "Visit your broker's website, then open Reports → Tax P&L.",
}


def get_guide(document_type: str, platform: str = "generic") -> dict[str, object]:
    if document_type not in GUIDE_DOCUMENT_TYPES:
        raise ValueError(f"document_type must be one of {', '.join(GUIDE_DOCUMENT_TYPES)}")

    guide_dir = files("itr_agent") / "guides_data"
    platform_key = platform.lower().replace("-", "_").replace(" ", "_")
    candidates = [f"{document_type}_{platform_key}.md", f"{document_type}.md"]

    for name in candidates:
        resource = guide_dir / name
        if resource.is_file():
            return {
                "document_type": document_type,
                "platform": platform,
                "platform_specific": name != f"{document_type}.md",
                "guide_markdown": resource.read_text(encoding="utf-8"),
            }

    return {
        "document_type": document_type,
        "platform": platform,
        "platform_specific": False,
        "guide_markdown": FALLBACK_HINTS[document_type],
    }

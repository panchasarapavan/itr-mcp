"""Local document store. Everything stays on the user's machine.

Layout: <root>/<assessment_year>/<document_type>/<key>.json

Each document type can hold several files, keyed by a short identifier: one
Form 16 per employer TAN, one broker statement per source. Re-ingesting the
same key replaces that file, so a corrected upload does not leave duplicates.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_KEY = "default"
DOCUMENT_TYPES = ("ais", "form26as", "form16", "broker_pnl")

_ASSESSMENT_YEAR = re.compile(r"\d{4}-\d{2}")
_KEY = re.compile(r"[a-z0-9_]{1,40}")


def make_key(raw: str) -> str:
    """Turn an employer TAN or broker name into a safe file key, e.g. 'Zerodha' -> 'zerodha'."""
    key = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return key[:40] or DEFAULT_KEY


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_env(cls) -> "Workspace":
        return cls(Path(os.environ.get("ITR_AGENT_HOME") or Path.home() / ".itr-agent"))

    def save(
        self,
        assessment_year: str,
        document_type: str,
        key: str,
        data: dict[str, Any],
    ) -> Path:
        path = self._path(assessment_year, document_type, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent / (path.name + ".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(path)
        return path

    def load(self, assessment_year: str, document_type: str, key: str = DEFAULT_KEY) -> dict[str, Any] | None:
        path = self._path(assessment_year, document_type, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def keys(self, assessment_year: str, document_type: str) -> list[str]:
        folder = self._folder(assessment_year, document_type)
        if not folder.is_dir():
            return []
        return sorted(path.stem for path in folder.glob("*.json"))

    def present_types(self, assessment_year: str) -> set[str]:
        return {doc_type for doc_type in DOCUMENT_TYPES if self.keys(assessment_year, doc_type)}

    def _folder(self, assessment_year: str, document_type: str) -> Path:
        if not _ASSESSMENT_YEAR.fullmatch(assessment_year):
            raise ValueError(f"assessment_year must look like 2026-27, got {assessment_year!r}")
        if document_type not in DOCUMENT_TYPES:
            raise ValueError(f"unknown document type {document_type!r}")
        return self.root / assessment_year / document_type

    def _path(self, assessment_year: str, document_type: str, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError(f"invalid document key {key!r}")
        return self._folder(assessment_year, document_type) / f"{key}.json"

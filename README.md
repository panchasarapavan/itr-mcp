# itr-agent

An open-source MCP server for filing Indian Income Tax Returns. It runs locally
on your machine and plugs into any MCP-capable AI app (Claude Desktop, Cursor,
and others). No backend, and no document leaves your device.

## Status

Phase 0 (foundation): strict schemas, the trade validation gate, and the MCP
server skeleton.

Phase 1 (AIS and missing documents) is in place:

- **Ingest and store.** `ingest_ais`, `ingest_26as`, `ingest_form16`, and
  `ingest_trades` take structured data that the AI has read from the user's
  file. The server validates it and stores it under `ITR_AGENT_HOME` (default
  `~/.itr-agent`), one folder per assessment year.
- **Show.** `show_ais` renders the AIS as markdown, with Indian digit grouping
  and TDS totals.
- **Find what's missing.** `get_document_checklist` works out which supporting
  documents the AIS implies (26AS, Form 16 per employer, broker P&L) and
  attaches a download guide to each missing one. Guides live in
  `src/itr_agent/guides_data/`. They are drafted and not yet checked against
  the live portals.

Still `not_implemented`: reconciliation, tax and capital-gains engines, ITR
JSON, and currency conversion. These are Phases 2 to 3.

## Development

```bash
uv venv .venv
uv pip install -p .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest
```

Run the server over stdio:

```bash
.venv/bin/itr-agent
```

## License

MIT. See [LICENSE](LICENSE).

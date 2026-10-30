# itr-agent

An open-source MCP server for filing Indian Income Tax Returns. It runs locally
on your machine and plugs into any MCP-capable AI app (Claude Desktop, Cursor,
and others). No backend, and no document leaves your device.

## Status

Phase 0 (foundation) is in place:

- `schemas.py`: strict Pydantic contracts (`NormalizedTrade`, `AISData`,
  `Form16Data`, `ReconciliationResult`). Unknown fields are rejected.
- `validation.py`: the Layer 2 gate. It checks quantity and price positivity,
  ISIN format and check digit, trade date, currency against exchange, asset
  class against exchange, sell-versus-holding, and duplicates. Errors block a
  batch. Warnings are advisory.
- `server.py`: the MCP server with all 14 tools registered. `ingest_trades` is
  live. The rest return `not_implemented` until their phase lands.

Engines (capital gains, tax, reconciliation, ITR JSON) come in Phases 1 to 3.

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

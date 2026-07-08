# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A standalone **Python / FastMCP gateway** that exposes the iSuccess external REST API
(`/api/external/v2/*`) to AI agents as read-only MCP tools. It runs over **stdio** — the
MCP client spawns this process locally and it calls the production API directly. It is a
separate project from the Production app (`isuccess-tool-ver3`) and depends on it only over
HTTP at runtime; there is no shared code. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first.

## Stack

- Python 3.10+ — **use 3.13**; the venv step fails on 3.14 (`ensurepip` broken).
- `fastmcp>=3.2,<4`, `httpx`, `python-dotenv`.

## Commands

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

TOOL_API_KEY=<vip_pro> .venv/bin/python mcp_gateway.py   # run the gateway (stdio)
TOOL_API_KEY=<vip_pro> .venv/bin/python test_client.py   # smoke test: spawn, list tools
```

End users install straight from GitHub — `uvx --from git+<repo> isuccess-external-mcp`
(entry point in `pyproject.toml`); see README. Config is env-driven; the process
**exits at startup** if `TOOL_API_KEY` is missing or the spec can't be fetched.

## Layout

- `mcp_gateway.py` — the entire server (config → `load_spec` → `build_server` → `main`).
- `pyproject.toml` — packages the module + the `isuccess-external-mcp` console script
  (what `uvx --from git+<repo>` runs).
- `test_client.py` — end-to-end check; spawns the module over stdio.
- `docs/ARCHITECTURE.md` — internals and the rationale for the decisions below.

## Critical invariants (do NOT break)

- **stdio only; `TOOL_API_KEY` is the only required env.** `TOOL_BASE_URL` /
  `SPEC_URL` default to production, so a local install supplies just the key. Don't
  reintroduce required vars for values that are the same for every user.
- **`from_openapi(..., validate_output=False)`** — the upstream contract is frozen and
  returns some numeric fields as strings; strict output validation would reject real data
  with "Output validation error". Keep it off.
- **Never commit secrets.** `.env` is git-ignored; the `vip_pro` key comes from env only
  (`--env TOOL_API_KEY=…` on `claude mcp add`, or `.env` when running from source).
- The upstream spec path is `/api/external/v2/openapi` — **no `.json`** (the web server
  serves `*.json` as a static asset, so it never reaches Tool).

## Conventions

- Keep it simple: one small server file, env-driven config, fail fast.
- Comments state the **why** (a constraint or gotcha), never the what.
- Don't add business logic here — the gateway is a pass-through. New upstream endpoints
  appear automatically after a restart; no code change.

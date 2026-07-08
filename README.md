# External MCP Gateway

A small Python gateway that exposes the **iSuccess external API**
(`/api/external/v2/*`) to AI agents as read-only Model Context Protocol (MCP) tools.

It fetches the aggregated OpenAPI spec once at startup and, via
[`FastMCP.from_openapi`](https://gofastmcp.com/integrations/openapi), turns every
documented endpoint into an MCP tool. It runs over **stdio** — the AI client (Claude
Code, Cursor, …) spawns the gateway locally and it calls the production API directly:

```
Claude Code ──spawn (stdio)──► gateway ──X-Api-Key (vip_pro)──► Tool API /api/external/v2/* ──► JSON
```

Each user installs it straight from GitHub with `uvx`; the only thing they supply is
the `vip_pro` API key. Everything else defaults to production.

> How it works internally and why the key settings exist: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
> Working on the code with Claude Code? See [CLAUDE.md](CLAUDE.md).

## Prerequisites (Tool side, one-time)

The gateway needs the spec at a URL it can reach with its API key. The internal docs
endpoint (`/api/v2/external-docs/openapi`) is session-gated, so add an **additive**
key-gated route (does not touch existing external routes):

```php
// routes/api/External/docs.php
<?php

use App\Http\Controllers\V2\External\ExternalDocsController;
use Illuminate\Support\Facades\Route;

// Aggregated OpenAPI spec for the MCP gateway. Same builder as the internal docs
// route, but authenticated by the vip_pro API key (not a Sanctum session). No
// `.json` suffix: the web server serves *.json paths as static assets, so such a
// path would never reach Tool routing.
Route::group([
    'prefix'     => 'external/v2',
    'middleware' => ['api.key:vip_pro', 'throttle:api-external'],
], function () {
    Route::get('/openapi', [ExternalDocsController::class, 'openapi'])
        ->name('external.docs.openapi');
});
```

Files under `routes/api/*/` are auto-loaded by `RouteServiceProvider`. The response is
the standard `{success, data}` envelope; the gateway unwraps `.data` automatically. Verify:

```bash
curl -H "X-Api-Key: <vip_pro-key>" https://production.trackingis.info/api/external/v2/openapi | head
```

## Install into an agent

One-time per machine — install [`uv`](https://docs.astral.sh/uv/) (provides `uvx`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # or: brew install uv
```

### Claude Code

```bash
claude mcp add isuccess-external -s user \
  --env TOOL_API_KEY=<vip_pro-key> \
  -- uvx --from git+https://github.com/iSuccess-corp/external-mcp-gateway.git isuccess-external-mcp
```

`uvx` fetches this repo from GitHub, builds an isolated environment, and runs the
gateway over stdio — no `git clone`, no venv. `-s user` makes it available in every
project. Restart Claude Code, then `/mcp` lists the tools; use them right away.

### Cursor / Claude Desktop

Both take a stdio `command` in their MCP config (Cursor: `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "isuccess-external": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/iSuccess-corp/external-mcp-gateway.git", "isuccess-external-mcp"],
      "env": { "TOOL_API_KEY": "<vip_pro-key>" }
    }
  }
}
```

## Run from source (contributing)

```bash
git clone https://github.com/iSuccess-corp/external-mcp-gateway.git
cd external-mcp-gateway
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
TOOL_API_KEY=<vip_pro-key> .venv/bin/python test_client.py   # spawns stdio, lists tools
```

`python mcp_gateway.py` runs the gateway directly (reads `.env` if present).

## Updating

The two kinds of change propagate differently:

- **New or changed API endpoints (backend).** The gateway re-fetches the OpenAPI spec on
  every start, so just **restart your client** — the new tools appear. No reinstall.
- **Gateway code (a new commit in this repo).** `uvx` caches the build per commit and does
  **not** auto-pull. To pick up an update, clear the cache once and restart your client:
  ```bash
  uv cache clean external-mcp-gateway   # then restart Claude Code
  ```

## Troubleshooting

**`Output validation error: 'X' is not of type 'integer'` on a tool call.** The OpenAPI
spec's declared response types don't always match what the frozen external API actually
returns (e.g. a count comes back as the string `"681"` against an `integer` schema). The
gateway calls `from_openapi(..., validate_output=False)` so responses pass through as-is
— do not flip this back on unless the upstream types are guaranteed to match the spec.

## Configuration reference

See `.env.example`. Only **`TOOL_API_KEY`** is required — `TOOL_BASE_URL` and
`SPEC_URL` default to production. The process **exits at startup** if the key is missing
or the spec cannot be fetched.

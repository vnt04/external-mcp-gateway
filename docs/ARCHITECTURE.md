# Architecture

A thin **FastMCP** gateway that turns the iSuccess external REST API
(`/api/external/v2/*`) into Model Context Protocol (MCP) tools for AI agents. It owns no
business logic — it fetches the upstream OpenAPI spec and lets FastMCP generate one tool
per endpoint. It runs over **stdio**: the MCP client spawns it locally.

## Data flow

```
  MCP client --spawn (stdio)--> gateway --X-Api-Key: vip_pro--> Tool API /api/external/v2/<path> --> JSON
```

1. **Startup** — on spawn, `load_spec()` fetches the aggregated spec (unwrapping
   the tool API's `{success, data}` envelope), then `FastMCP.from_openapi(spec, client)`
   builds one tool per operation. Add an endpoint upstream → restart; no code change.
2. **Request** — the client calls a tool over stdio. The gateway injects the
   **`X-Api-Key`** (`vip_pro`) on the upstream call and returns the JSON as-is. The
   client already owns the local process, so there is no separate client-auth layer.

## Components (`mcp_gateway.py`)

| Piece | Responsibility |
| --- | --- |
| Config block (`_env`) | Read env, fail fast if a required var is missing. |
| `load_spec()` | Fetch the OpenAPI spec; unwrap the `{success, data}` envelope. |
| `build_server()` | Build the httpx client (base URL + `X-Api-Key`) and call `from_openapi(..., validate_output=False)`. |
| `main()` | `mcp.run(transport="stdio")` — the console-script entry point. |

## Key decisions (do not revert without cause)

1. **stdio + local self-host** — the target user is an internal teammate who installs
   from GitHub (`uvx --from git+<repo> isuccess-external-mcp`) and runs the gateway
   locally. `TOOL_BASE_URL` / `SPEC_URL` default to production, so the only thing they
   supply is `TOOL_API_KEY`. Trade-off: each local runner holds the `vip_pro` key —
   acceptable for an internal team, not for external partners.
2. **`validate_output=False`** — the external contract is frozen (other live products
   consume it) and its responses sometimes return a numeric-looking value as a string
   (e.g. `"681"` against an `integer` schema). Strict output validation would reject that
   real data with *"Output validation error"*. Permissive mode passes JSON through.
3. **Spec path has no `.json` suffix** (`/api/external/v2/openapi`) — the web server
   serves any `*.json` path as a static asset, so `openapi.json` would never reach
   Tool routing.

## Upstream (the Tool side)

- **Spec**: key-gated `GET /api/external/v2/openapi` — route `routes/api/External/docs.php`
  in the `isuccess-tool-ver3` repo, reusing `ExternalDocsController@openapi`. Returns the
  `{success, data}` envelope; this gateway reads `.data`.
- **Data**: `GET /api/external/v2/*`, `api.key:vip_pro` middleware, `X-Api-Key` header.

## Security model

- Each user's local gateway holds the `vip_pro` key (via `--env` / `.env`) and calls
  the tool API directly. There is no per-user revocation — rotate the key to cut access.
  Fit for an internal team, not external partners.
- **No secrets in git**: `.env` is git-ignored; the `vip_pro` key is injected via env only.

## Extending

- **New upstream endpoint** → nothing here; restart to re-fetch the spec.
- **New config** → prefer a sensible default over a required var (see decision 1).

Client-install steps live in [../README.md](../README.md).

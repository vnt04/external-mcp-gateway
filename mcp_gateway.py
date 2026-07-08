"""External MCP Gateway for the iSuccess external API.

Fetches the aggregated OpenAPI spec at startup and auto-generates one read-only MCP
tool per documented endpoint via ``FastMCP.from_openapi``. Runs over stdio — the MCP
client (Claude Code, Cursor, ...) spawns this process locally and it calls the
production API directly. Adding an endpoint upstream needs only a restart — no code
change here.

Auth: the ``vip_pro`` key (TOOL_API_KEY), sent to the tool API as the API-key header on
every request. The MCP client owns the spawned process, so there is no client-side auth.
"""

from __future__ import annotations

import os
import sys

import httpx
from fastmcp import FastMCP

try:  # local dev convenience; env is normally passed by the MCP client
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"[mcp-gateway] Missing required env var: {name}")
    return value or ""


# --- Configuration (fail fast at startup) ------------------------------------
# Base URL of the external API surface — the OpenAPI `servers[0].url`. Spec paths are
# relative to it (e.g. `/amazon/report-total`), so it MUST end in `.../api/external/v2`.
# Defaulted to production so a local install only has to supply TOOL_API_KEY.
TOOL_BASE_URL = _env("TOOL_BASE_URL", "https://production.trackingis.info/api/external/v2").rstrip("/")
# Where the aggregated spec is served (key-gated). Derived from the base URL.
SPEC_URL = _env("SPEC_URL", f"{TOOL_BASE_URL}/openapi")
# vip_pro key sent to the tool API as the API-key header — the one secret each user provides.
TOOL_API_KEY = _env("TOOL_API_KEY", required=True)
API_KEY_HEADER = _env("API_KEY_HEADER", "X-Api-Key")
UPSTREAM_TIMEOUT = float(_env("UPSTREAM_TIMEOUT", "60"))
SERVER_NAME = _env("MCP_SERVER_NAME", "iSuccess External API")


def load_spec() -> dict:
    """Fetch the OpenAPI spec, unwrapping the tool API's ``{success, data}`` envelope if present."""
    try:
        resp = httpx.get(
            SPEC_URL,
            headers={API_KEY_HEADER: TOOL_API_KEY},
            timeout=UPSTREAM_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        sys.exit(f"[mcp-gateway] Could not fetch OpenAPI spec from {SPEC_URL}: {exc}")

    payload = resp.json()
    if "openapi" not in payload and isinstance(payload.get("data"), dict):
        payload = payload["data"]  # {success, data} success-response wrapper

    if "openapi" not in payload:
        sys.exit("[mcp-gateway] Fetched document is not an OpenAPI spec (no 'openapi' key).")

    return payload


def build_server() -> FastMCP:
    spec = load_spec()

    upstream = httpx.AsyncClient(
        base_url=TOOL_BASE_URL,
        headers={API_KEY_HEADER: TOOL_API_KEY},
        timeout=UPSTREAM_TIMEOUT,
    )

    # The external surface is entirely read-only GETs, and FastMCP's default route
    # mapping already turns every route into a Tool — no custom route_maps needed.
    #
    # validate_output=False: the external API contract is frozen (other live products
    # consume it), so we cannot retype its responses to match the spec — and the spec's
    # declared types don't always match reality (e.g. a count returned as the string
    # "681" against an `integer` schema). Strict output validation would reject that real
    # data with "Output validation error". Permissive mode passes the JSON through as-is.
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=upstream,
        name=SERVER_NAME,
        validate_output=False,
    )


mcp = build_server()


def main() -> None:
    """Console-script entry point (``isuccess-external-mcp``) and ``python mcp_gateway.py``.

    stdio: the MCP client spawns and owns this process (local self-host install).
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

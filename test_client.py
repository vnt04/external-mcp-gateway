"""End-to-end check: spawn the local (stdio) gateway, list its tools, ping.

Reads the env the gateway needs (TOOL_API_KEY at minimum). Run from the repo:
    TOOL_API_KEY=<vip_pro> .venv/bin/python test_client.py
"""

import asyncio

from fastmcp import Client

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


async def main() -> None:
    # Spawns `python mcp_gateway.py` over stdio; the child inherits this process's env.
    async with Client("mcp_gateway.py") as client:
        await client.ping()
        tools = await client.list_tools()
        print(f"Connected (stdio: mcp_gateway.py) — {len(tools)} tools")
        for tool in tools:
            print(f"  - {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())

"""Smoke test del server MCP Streamable HTTP.

Avvia l'app ASGI in-process (via httpx ASGITransport) e verifica:

* ``/health`` risponde senza autenticazione.
* ``/mcp`` richiede Bearer token.
* Con token valido, una richiesta ``initialize`` MCP viene accettata
  dallo StreamableHTTPSessionManager.
* ``tools/list`` restituisce i 5 tool previsti.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp_server.http import create_app  # noqa: E402

WIKI = ROOT / "wiki"
TOKEN = "smoke-secret-12345"


def build_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=True,
    )


async def main() -> int:
    app = create_app(wiki_root=WIKI, token=TOKEN, json_response=True, stateless=True)

    # httpx ASGITransport non triggera il lifespan: lo facciamo a mano.
    async with app.router.lifespan_context(app), build_client(app) as client:
        # 1) Health senza auth
        r = await client.get("/health")
        assert r.status_code == 200, (r.status_code, r.text)
        data = r.json()
        assert data["status"] == "ok"
        assert data["transport"] == "streamable-http"
        assert data["auth"] is True
        print(f"[OK] /health senza auth: {data}")

        # 2) /mcp senza auth -> 401
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        assert r.status_code == 401, (r.status_code, r.text)
        print(f"[OK] /mcp senza auth: 401 ({r.headers.get('www-authenticate')})")

        # 3) /mcp con token sbagliato -> 403
        r = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer wrong-token"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        assert r.status_code == 403, (r.status_code, r.text)
        print("[OK] /mcp con token sbagliato: 403")

        # 4) /mcp con token valido + initialize MCP
        r = await client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-http", "version": "0.1.0"},
                },
            },
        )
        assert r.status_code in (200, 202), (r.status_code, r.text)
        print(f"[OK] /mcp initialize: HTTP {r.status_code}")

        # 5) /mcp con token valido + tools/list
        r = await client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            },
        )
        assert r.status_code in (200, 202), (r.status_code, r.text)
        body = r.text
        if body.startswith("data: "):
            payload = json.loads(body[len("data: "):].splitlines()[0])
        else:
            payload = (
                r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else json.loads(body)
            )
        tools = payload.get("result", {}).get("tools", [])
        names = {t["name"] for t in tools}
        expected = {"list_pages", "read_page", "search", "write_page", "append_note"}
        assert expected <= names, (names, expected)
        print(f"[OK] /mcp tools/list: {sorted(names)}")

    print("\nTUTTO OK — server MCP Streamable HTTP funzionante.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

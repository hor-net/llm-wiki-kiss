"""Server MCP con trasporto **Streamable HTTP** (MCP 2025).

Questo modulo espone gli stessi cinque tool del trasporto stdio
(``list_pages``, ``read_page``, ``search``, ``write_page``,
``append_note``) via HTTPS, in modo che client MCP in cloud (Open Cloud,
client MCP-aware aggiornati) possano connettersi senza dover lanciare un
sottoprocesso locale.

Architettura
------------
* ``mcp.server.streamable_http_manager.StreamableHTTPSessionManager``
  gestisce la negoziazione del protocollo MCP 2025-06-18.
* Tutta la logica di dominio resta in :mod:`wiki_core` (lo stesso
  ``WikiStorage`` usato dal server stdio).
* Autenticazione opzionale con **Bearer token** via
  :class:`BearerAuthMiddleware`. Il token si configura con la variabile
  d'ambiente ``WIKI_MCP_TOKEN``.

Esempio di avvio (vedi ``scripts/start-mcp-http.sh``):

    WIKI_MCP_TOKEN=segreto uvicorn mcp_server.http:app \\
        --host 0.0.0.0 --port 8766
"""

from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from wiki_core import WikiStorage, WikiStorageError

from .server import (
    _HANDLERS,
    ALL_TOOLS,
    SERVER_INSTRUCTIONS,
    _resolve_root_from_env,
)

LOGGER = logging.getLogger("mcp_server.http")

DEFAULT_MCP_PATH = "/mcp"
DEFAULT_MCP_HTTP_PORT = 8766


# ----------------------------------------------------------------------
# Autenticazione
# ----------------------------------------------------------------------


class BearerAuthMiddleware:
    """Middleware ASGI puro che richiede un Bearer token per le route MCP.

    Se ``expected_token`` è ``None`` o vuoto, l'autenticazione è
    disabilitata (utile per sviluppo locale). Le route ``/health`` e
    ``/healthz`` sono sempre esenti. La route ``/`` (info sul servizio)
    richiede auth se un token è configurato: se vuoi renderla pubblica,
    sposta l'endpoint di info sotto ``/health``.
    """

    EXEMPT_PATHS = {"/health", "/healthz"}

    def __init__(self, app: ASGIApp, expected_token: str | None) -> None:
        self.app = app
        self.expected_token = (expected_token or "").strip() or None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.expected_token is None:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        # Estrai l'header authorization dallo scope ASGI.
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1", errors="replace")
        if not auth.lower().startswith("bearer "):
            await self._reject(send, 401, "missing_bearer_token")
            return
        presented = auth[7:].strip()
        if not hmac.compare_digest(presented, self.expected_token):
            await self._reject(send, 403, "invalid_bearer_token")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, status: int, error: str) -> None:
        import json

        body = json.dumps({"error": error}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


# ----------------------------------------------------------------------
# Costruzione del server MCP (riusa gli stessi handler dello stdio)
# ----------------------------------------------------------------------


def _build_mcp_server(wiki_root: str | os.PathLike[str]) -> Server:
    storage = WikiStorage(wiki_root)
    server = Server("wiki-kiss-http", instructions=SERVER_INSTRUCTIONS)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list(ALL_TOOLS)

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent]:
        args = arguments or {}
        try:
            handler = _HANDLERS[name]
        except KeyError as exc:
            raise ValueError(f"Tool sconosciuto: {name}") from exc
        try:
            payload = handler(storage, args)
        except WikiStorageError as exc:
            LOGGER.warning("Tool %s fallito: %s", name, exc)
            raise ValueError(str(exc)) from exc
        return _to_text_content(payload)

    return server


def _to_text_content(payload) -> list[types.TextContent]:
    import json

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return [types.TextContent(type="text", text=text)]


# ----------------------------------------------------------------------
# Factory dell'app Starlette
# ----------------------------------------------------------------------


def create_app(
    wiki_root: str | os.PathLike[str] | None = None,
    token: str | None = None,
    mcp_path: str = DEFAULT_MCP_PATH,
    json_response: bool = True,
    stateless: bool = True,
) -> Starlette:
    """Crea l'app ASGI per il server MCP Streamable HTTP.

    Parameters
    ----------
    wiki_root:
        Cartella del wiki. Default: ``WIKI_ROOT`` env o ``./wiki``.
    token:
        Bearer token atteso. Default: ``WIKI_MCP_TOKEN`` env. Se nullo,
        l'autenticazione è disabilitata.
    mcp_path:
        Path HTTP su cui montare l'endpoint MCP (default ``/mcp``).
    json_response:
        Se True, il server risponde con JSON puro (no SSE). Default True.
    stateless:
        Se True, ogni richiesta è indipendente. Default True (più
        semplice per client cloud). Se False, il server mantiene sessioni.
    """
    root = wiki_root or _resolve_root_from_env()
    expected_token = token if token is not None else os.environ.get("WIKI_MCP_TOKEN")
    LOGGER.info(
        "Avvio MCP Streamable HTTP (path=%s, json=%s, stateless=%s, auth=%s)",
        mcp_path,
        json_response,
        stateless,
        "off" if not expected_token else "on",
    )

    mcp_server = _build_mcp_server(root)
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=json_response,
        stateless=stateless,
    )

    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "transport": "streamable-http",
                "wiki_root": str(root),
                "mcp_path": mcp_path,
                "auth": bool(expected_token),
            }
        )

    async def _root_index(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "name": "wiki-kiss MCP server (Streamable HTTP)",
                "mcp_endpoint": mcp_path,
                "tools": [t.name for t in ALL_TOOLS],
                "auth": bool(expected_token),
            }
        )

    async def _not_found(_request: Request, exc=None) -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404)

    inner_app = Starlette(
        routes=[
            Route("/", _root_index, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            Route("/healthz", health, methods=["GET"]),
            Mount(mcp_path, app=session_manager.handle_request),
        ],
    )

    # Auth middleware wrappa inner_app. Solo /health e /healthz sono esenti.
    # Per il resto (incluso / e /mcp), se il token è configurato, è richiesto.
    final_app = Starlette(
        lifespan=lifespan,  # stesso lifespan dell'inner, con session_manager.run()
        routes=[Mount("/", app=inner_app)],
        middleware=[
            Middleware(BearerAuthMiddleware, expected_token=expected_token)
        ]
        if expected_token
        else [],
    )
    return final_app


def _resolve_token() -> str | None:
    raw = os.environ.get("WIKI_MCP_TOKEN")
    return raw.strip() if raw else None


# L'app di default usabile da ``uvicorn mcp_server.http:app``.
app = create_app(token=_resolve_token())


# ----------------------------------------------------------------------
# Entry point CLI
# ----------------------------------------------------------------------


def main() -> int:
    """Entry point per ``python -m mcp_server.http``."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(
        prog="wiki-kiss-mcp-http",
        description=(
            "Server MCP Streamable HTTP (per client MCP in cloud). "
            "Supporta autenticazione Bearer via WIKI_MCP_TOKEN."
        ),
    )
    parser.add_argument("--host", default=os.environ.get("WIKI_HTTP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WIKI_HTTP_PORT", DEFAULT_MCP_HTTP_PORT)))
    parser.add_argument("--root", default=None, help="Cartella wiki (default: $WIKI_ROOT o ./wiki).")
    parser.add_argument("--mcp-path", default=os.environ.get("WIKI_MCP_PATH", DEFAULT_MCP_PATH))
    parser.add_argument("--log-level", default=os.environ.get("WIKI_LOG_LEVEL", "INFO"))
    parser.add_argument("--stateless", action="store_true", default=True)
    parser.add_argument("--no-stateless", dest="stateless", action="store_false")
    parser.add_argument("--json-response", action="store_true", default=True)
    parser.add_argument("--no-json-response", dest="json_response", action="store_false")
    parser.add_argument("--token", default=None, help="Bearer token (default: $WIKI_MCP_TOKEN).")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    application = create_app(
        wiki_root=args.root,
        token=args.token,
        mcp_path=args.mcp_path,
        json_response=args.json_response,
        stateless=args.stateless,
    )
    uvicorn.run(
        application,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        access_log=True,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

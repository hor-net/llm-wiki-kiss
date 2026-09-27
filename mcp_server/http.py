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
* Autenticazione obbligatoria con **Bearer token** via
  :class:`BearerAuthMiddleware`. Il token si configura con la variabile
  d'ambiente ``WIKI_MCP_TOKEN``.

Esempio di avvio (vedi ``scripts/start-mcp-http.sh``):

    scripts/configure.sh --https on --cert server.crt --key server.key
"""

from __future__ import annotations

import asyncio
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

from wiki_core import WikiStorage, WikiStorageError

from .auth import BearerAuthMiddleware
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
            payload = await asyncio.to_thread(handler, storage, args)
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
        Bearer token atteso. Default: ``WIKI_MCP_TOKEN`` env. Se assente,
        il server resta fail-closed e risponde 503.
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
        "missing (fail-closed)" if not expected_token else "on",
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
            {"status": "ok", "transport": "streamable-http"}
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

    # Il middleware resta fail-closed se il token non è configurato.
    final_app = Starlette(
        lifespan=lifespan,  # stesso lifespan dell'inner, con session_manager.run()
        routes=[Mount("/", app=inner_app)],
        middleware=[Middleware(BearerAuthMiddleware, expected_token=expected_token)],
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
            "Richiede autenticazione Bearer via WIKI_MCP_TOKEN."
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
    parser.add_argument("--cert", default=os.environ.get("WIKI_TLS_CERT"))
    parser.add_argument("--key", default=os.environ.get("WIKI_TLS_KEY"))
    args = parser.parse_args()
    effective_token = (args.token or _resolve_token() or "").strip()
    if os.environ.get("WIKI_HTTPS_ENABLED", "0") != "1":
        parser.error("Interfaccia HTTPS disabilitata; usa scripts/configure.sh --https on.")
    if not effective_token:
        parser.error("Bearer token obbligatorio: usa --token o WIKI_MCP_TOKEN.")
    if not args.cert or not os.path.isfile(args.cert):
        parser.error("Certificato TLS mancante o non leggibile.")
    if not args.key or not os.path.isfile(args.key):
        parser.error("Chiave TLS mancante o non leggibile.")

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    application = create_app(
        wiki_root=args.root,
        token=effective_token,
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
        ssl_certfile=args.cert,
        ssl_keyfile=args.key,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

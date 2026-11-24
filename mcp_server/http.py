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
* Autenticazione obbligatoria: Bearer statico di default, oppure OAuth
  con accesso in sola lettura (``WIKI_MCP_AUTH_MODE=oauth``).

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
from starlette.types import Receive, Scope, Send

from wiki_core import WikiStorage, WikiStorageError

from .auth import BearerAuthMiddleware
from .oauth import METADATA_PREFIX, OAuthMiddleware, OAuthSettings
from .server import (
    _HANDLERS,
    ALL_TOOLS,
    SERVER_INSTRUCTIONS,
    SKILL_NAMES,
    _load_skill,
    _resolve_root_from_env,
)

LOGGER = logging.getLogger("mcp_server.http")

DEFAULT_MCP_PATH = "/mcp"
DEFAULT_MCP_HTTP_PORT = 8766
READ_ONLY_TOOLS = frozenset({"list_pages", "read_page", "search"})


# ----------------------------------------------------------------------
# MCP server construction (reuses the same stdio handlers)
# ----------------------------------------------------------------------


def _build_mcp_server(wiki_root: str | os.PathLike[str], *, read_only: bool = False) -> Server:
    storage = WikiStorage(wiki_root)
    instructions = "Read and search pages in the configured wiki." if read_only else SERVER_INSTRUCTIONS
    server = Server("wiki-kiss-http", instructions=instructions)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [tool for tool in ALL_TOOLS if not read_only or tool.name in READ_ONLY_TOOLS]

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent]:
        if read_only and name not in READ_ONLY_TOOLS:
            raise ValueError("Tool not available in read-only mode")
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

    if read_only:
        return server

    @server.list_prompts()
    async def _list_prompts():
        """Expose wiki skills as MCP prompts (server-side, no install)."""
        prompts = []
        for skill_name in SKILL_NAMES:
            try:
                _, description, _ = _load_skill(skill_name)
            except FileNotFoundError:
                LOGGER.warning("Skill %s non trovata, skip", skill_name)
                continue
            prompts.append(
                types.Prompt(
                    name=skill_name,
                    description=description,
                    arguments=[],
                )
            )
        return prompts

    @server.get_prompt()
    async def _get_prompt(name, arguments):
        """Return the body of a skill prompt loaded from SKILL.md."""
        if name not in SKILL_NAMES:
            raise ValueError("Prompt sconosciuto: " + name)
        try:
            _, description, body = _load_skill(name)
        except FileNotFoundError as exc:
            raise ValueError("Skill " + name + " non disponibile") from exc
        return types.GetPromptResult(
            description=description,
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=body),
                )
            ],
        )

    return server


def _to_text_content(payload) -> list[types.TextContent]:
    import json

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return [types.TextContent(type="text", text=text)]


# ----------------------------------------------------------------------
# Starlette app factory
# ----------------------------------------------------------------------


class _McpEndpoint:
    """Serve the public OAuth resource path directly, without a slash redirect."""

    def __init__(self, manager: StreamableHTTPSessionManager) -> None:
        self.manager = manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.manager.handle_request(scope, receive, send)


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
        If True, each request is independent. Default True (simpler for
        simpler for cloud clients). If False, the server keeps sessions.
    """
    root = wiki_root or _resolve_root_from_env()
    oauth = OAuthSettings.from_env(mcp_path)
    expected_token = token if token is not None else os.environ.get("WIKI_MCP_TOKEN")
    auth_mode = "oauth (read-only)" if oauth else "bearer" if expected_token else "missing (fail-closed)"
    LOGGER.info(
        "Avvio MCP Streamable HTTP (path=%s, json=%s, stateless=%s, auth=%s)",
        mcp_path,
        json_response,
        stateless,
        auth_mode,
    )

    mcp_server = _build_mcp_server(root, read_only=oauth is not None)
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
                "tools": [t.name for t in ALL_TOOLS if not oauth or t.name in READ_ONLY_TOOLS],
                "auth": bool(oauth or expected_token),
            }
        )

    routes = [
        Route("/", _root_index, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/healthz", health, methods=["GET"]),
    ]
    if oauth:
        async def metadata(_request: Request) -> JSONResponse:
            return JSONResponse(oauth.metadata())

        resource_path = mcp_path.rstrip("/")
        endpoint = _McpEndpoint(session_manager)
        routes.extend([
            Route(oauth.metadata_path, metadata, methods=["GET"]),
            Route(METADATA_PREFIX, metadata, methods=["GET"]),
            Route(resource_path, endpoint),
            Route(resource_path + "/", endpoint),
        ])
        middleware = Middleware(OAuthMiddleware, settings=oauth)
    else:
        routes.append(Mount(mcp_path, app=session_manager.handle_request))
        middleware = Middleware(BearerAuthMiddleware, expected_token=expected_token)
    return Starlette(lifespan=lifespan, routes=routes, middleware=[middleware])


def _resolve_token() -> str | None:
    raw = os.environ.get("WIKI_MCP_TOKEN")
    return raw.strip() if raw else None


# L'app di default usabile da ``uvicorn mcp_server.http:app``.
app = create_app(mcp_path=os.environ.get("WIKI_MCP_PATH", DEFAULT_MCP_PATH))


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
            "Autenticazione Bearer statica o OAuth in sola lettura."
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
    if os.environ.get("WIKI_MCP_AUTH_MODE", "bearer") == "bearer" and not effective_token:
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

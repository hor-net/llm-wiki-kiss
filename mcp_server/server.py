"""MCP server implementation for the KISS wiki.

Default transport: ``stdio``. Other transports can be obtained by
importing :func:`build_server` and managing the lifecycle manually.

Every tool is declared with an explicit JSON schema so that any
compatible client (Open Cloud, Claude Code, Perplexity, ...) can negotiate
capabilities without manual setup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.shared.exceptions import McpError

from wiki_core import (
    WikiStorage,
    WikiStorageError,
)

LOGGER = logging.getLogger("mcp_server")
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "wiki"

SERVER_INSTRUCTIONS = (
    "Self-hosted KISS wiki. Use the tools to read, write and search "
    "Markdown/HTML pages in the configured wiki folder. Paths are "
    "relative to the wiki root and use '/' as the separator."
)


# ----------------------------------------------------------------------
# Declarative tool definitions
# ----------------------------------------------------------------------

TOOL_LIST_PAGES: types.Tool = types.Tool(
    name="list_pages",
    description=(
        "Lists all the pages in the wiki (.md/.html files). "
        "Optionally accepts a subfolder."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "Optional relative subfolder.",
            }
        },
        "additionalProperties": False,
    },
)

TOOL_READ_PAGE: types.Tool = types.Tool(
    name="read_page",
    description=(
        "Reads the content of a wiki page given the relative "
        "path (e.g. 'notes/example-note.md')."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path of the page, with extension.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
)

TOOL_SEARCH: types.Tool = types.Tool(
    name="search",
    description=(
        "Simple full-text search (case-insensitive by default) "
        "across all wiki pages."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "String to search for.",
            },
            "subdir": {
                "type": "string",
                "description": "Restrict the search to a subfolder.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "description": "Maximum number of matches returned.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "If true, the search is case-sensitive.",
                "default": False,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)

TOOL_WRITE_PAGE: types.Tool = types.Tool(
    name="write_page",
    description=(
        "Creates or overwrites a wiki page. If the extension is missing "
        ".md is added."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path of the page.",
            },
            "content": {
                "type": "string",
                "description": "Markdown/HTML content of the page.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "If false, refuses to write when the page exists.",
                "default": True,
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
)

TOOL_APPEND_NOTE: types.Tool = types.Tool(
    name="append_note",
    description=(
        "Quickly appends a note or log entry. If 'path' is omitted, "
        "the note is appended to the current day's log file "
        "(wiki/logs/YYYY-MM-DD.md)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Text of the note.",
            },
            "path": {
                "type": "string",
                "description": "Optional target page.",
            },
            "heading": {
                "type": "string",
                "description": "Optional level-2 heading.",
            },
        },
        "required": ["content"],
        "additionalProperties": False,
    },
)

ALL_TOOLS: tuple[types.Tool, ...] = (
    TOOL_LIST_PAGES,
    TOOL_READ_PAGE,
    TOOL_SEARCH,
    TOOL_WRITE_PAGE,
    TOOL_APPEND_NOTE,
)


# ----------------------------------------------------------------------
# Server factory
# ----------------------------------------------------------------------

def build_server(root: str | os.PathLike[str] | None = None) -> Server:
    """Builds and configures an instance of :class:`mcp.server.Server`."""
    wiki_root = Path(root) if root else _resolve_root_from_env()
    storage = WikiStorage(wiki_root)
    server = Server(
        "wiki-kiss",
        instructions=SERVER_INSTRUCTIONS,
    )
    _register_handlers(server, storage)
    return server


def _resolve_root_from_env() -> Path:
    raw = os.environ.get("WIKI_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_ROOT


def _register_handlers(server: Server, storage: WikiStorage) -> None:
    """Registra i decorator ``list_tools`` e ``call_tool`` sul server."""

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list(ALL_TOOLS)

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        args = arguments or {}
        try:
            handler = _HANDLERS[name]
        except KeyError as exc:
            raise McpError(f"Tool sconosciuto: {name}") from exc
        try:
            payload = await asyncio.to_thread(handler, storage, args)
        except WikiStorageError as exc:
            LOGGER.warning("Tool %s fallito: %s", name, exc)
            raise McpError(str(exc)) from exc
        return _to_text_content(payload)


# ----------------------------------------------------------------------
# Implementazione dei singoli tool
# ----------------------------------------------------------------------

def _tool_list_pages(storage: WikiStorage, args: dict) -> dict:
    pages = storage.list_pages(subdir=args.get("subdir"))
    return {
        "count": len(pages),
        "pages": [
            {
                "path": p.path,
                "title": p.title,
                "size": p.size,
                "modified": p.modified,
                "extension": p.extension,
            }
            for p in pages
        ],
    }


def _tool_read_page(storage: WikiStorage, args: dict) -> dict:
    path = args.get("path")
    if not path:
        raise WikiStorageError("Parametro 'path' obbligatorio.")
    content = storage.read_page(path)
    return {
        "path": storage._normalize_path(path),
        "length": len(content),
        "content": content,
    }


def _tool_search(storage: WikiStorage, args: dict) -> dict:
    query = args.get("query")
    if not query:
        raise WikiStorageError("Parametro 'query' obbligatorio.")
    results = storage.search(
        query=query,
        subdir=args.get("subdir"),
        max_results=int(args.get("max_results", 50)),
        case_sensitive=bool(args.get("case_sensitive", False)),
    )
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "path": r.path,
                "line": r.line_number,
                "matches": r.matches,
                "snippet": r.snippet,
            }
            for r in results
        ],
    }


def _tool_write_page(storage: WikiStorage, args: dict) -> dict:
    path = args.get("path")
    content = args.get("content", "")
    overwrite = bool(args.get("overwrite", True))
    if not path:
        raise WikiStorageError("Parametro 'path' obbligatorio.")
    info = storage.write_page(rel_path=path, content=content, overwrite=overwrite)
    return {
        "path": info.path,
        "title": info.title,
        "size": info.size,
        "modified": info.modified,
    }


def _tool_append_note(storage: WikiStorage, args: dict) -> dict:
    content = args.get("content")
    if not content:
        raise WikiStorageError("Parametro 'content' obbligatorio.")
    info = storage.append_note(
        content=content,
        rel_path=args.get("path"),
        heading=args.get("heading"),
    )
    return {
        "path": info.path,
        "title": info.title,
        "size": info.size,
        "modified": info.modified,
    }


_HANDLERS: dict[str, Any] = {
    "list_pages": _tool_list_pages,
    "read_page": _tool_read_page,
    "search": _tool_search,
    "write_page": _tool_write_page,
    "append_note": _tool_append_note,
}


def _to_text_content(payload: Any) -> list[types.TextContent]:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return [types.TextContent(type="text", text=text)]


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

async def run(root: str | os.PathLike[str] | None = None) -> None:
    """Starts the MCP server in ``stdio`` mode."""
    server = build_server(root)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-kiss-mcp",
        description="MCP server for the self-hosted KISS wiki.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Cartella radice del wiki (default: ./wiki o $WIKI_ROOT).",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("WIKI_LOG_LEVEL", "INFO"),
        help="Livello di logging (default: INFO).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        asyncio.run(run(args.root))
    except KeyboardInterrupt:
        LOGGER.info("Server interrotto dall'utente.")
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Minimal REST API for the KISS wiki.

Acts as a fallback to the MCP server for clients that do not support MCP.
Exposes the same five base operators over HTTP, plus ``/health`` and
``/stats``. Recommended start:

    WIKI_MCP_TOKEN=secret uvicorn rest_api:app --host 127.0.0.1 --port 8765

The wiki root is configurable via ``WIKI_ROOT``. Access requires the
``WIKI_MCP_TOKEN`` Bearer token; without a token the application stays
fail-closed.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query  # noqa: B008
from pydantic import BaseModel, Field
from starlette.middleware import Middleware

from mcp_server.auth import BearerAuthMiddleware
from wiki_core import (
    InvalidPathError,
    PageAlreadyExistsError,
    PageNotFoundError,
    WikiStorage,
    WikiStorageError,
    WriteLockTimeoutError,
)

DEFAULT_ROOT = Path(__file__).resolve().parent / "wiki"


# ----------------------------------------------------------------------
# Pydantic models (defined at module level to avoid forward reference issues).
# ----------------------------------------------------------------------


class PageOut(BaseModel):
    path: str
    title: str
    size: int
    modified: float
    extension: str


class PageListOut(BaseModel):
    count: int
    pages: list[PageOut]


class PageContentOut(BaseModel):
    path: str
    length: int
    content: str


class SearchHit(BaseModel):
    path: str
    line: int = Field(..., description="Line number, 1-based.")
    matches: int
    snippet: str


class SearchOut(BaseModel):
    query: str
    count: int
    results: list[SearchHit]


class WritePageIn(BaseModel):
    content: str
    overwrite: bool = True


class AppendNoteIn(BaseModel):
    content: str
    path: str | None = None
    heading: str | None = None


# ----------------------------------------------------------------------
# App factory
# ----------------------------------------------------------------------


def create_app(
    root: os.PathLike[str] | str | None = None,
    token: str | None = None,
) -> FastAPI:
    """FastAPI app factory, protected by the same token as the MCP server."""
    wiki_root = (
        Path(root).expanduser().resolve()
        if root
        else Path(os.environ.get("WIKI_ROOT", DEFAULT_ROOT)).expanduser().resolve()
    )
    storage = WikiStorage(wiki_root)
    expected_token = token if token is not None else os.environ.get("WIKI_MCP_TOKEN")

    app = FastAPI(
        title="Wiki KISS API",
        version="0.3.0",
        description=(
            "Fallback HTTP for the KISS wiki. Mirrors the base MCP tools."
        ),
        middleware=[Middleware(
            BearerAuthMiddleware,
            expected_token=expected_token,
        )],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "transport": "rest"}

    @app.get("/stats")
    def stats() -> dict:
        return storage.stats()

    @app.get("/pages", response_model=PageListOut)
    def list_pages(subdir: str | None = None) -> PageListOut:
        pages = storage.list_pages(subdir=subdir)
        return PageListOut(
            count=len(pages),
            pages=[
                PageOut(
                    path=p.path,
                    title=p.title,
                    size=p.size,
                    modified=p.modified,
                    extension=p.extension,
                )
                for p in pages
            ],
        )

    @app.get("/pages/{page_path:path}", response_model=PageContentOut)
    def read_page(page_path: str) -> PageContentOut:  # noqa: B009
        try:
            content = storage.read_page(page_path)
        except PageNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except WikiStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return PageContentOut(
            path=storage._normalize_path(page_path),
            length=len(content),
            content=content,
        )

    @app.put("/pages/{page_path:path}", response_model=PageOut)
    def write_page(
        page_path: str,
        body: WritePageIn = Body(...),  # noqa: B008
    ) -> PageOut:  # noqa: B009
        try:
            info = storage.write_page(
                rel_path=page_path, content=body.content, overwrite=body.overwrite
            )
        except PageAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WriteLockTimeoutError as exc:
            raise HTTPException(
                status_code=503, detail=str(exc), headers={"Retry-After": "1"}
            ) from exc
        except InvalidPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except WikiStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return PageOut(
            path=info.path,
            title=info.title,
            size=info.size,
            modified=info.modified,
            extension=info.extension,
        )

    @app.get("/search", response_model=SearchOut)
    def search(
        q: str = Query(..., min_length=1, description="Text to search for."),  # noqa: B008
        subdir: str | None = None,
        max_results: int = Query(50, ge=1, le=500),  # noqa: B008
        case_sensitive: bool = False,
    ) -> SearchOut:
        results = storage.search(
            query=q,
            subdir=subdir,
            max_results=max_results,
            case_sensitive=case_sensitive,
        )
        return SearchOut(
            query=q,
            count=len(results),
            results=[
                SearchHit(
                    path=r.path,
                    line=r.line_number,
                    matches=r.matches,
                    snippet=r.snippet,
                )
                for r in results
            ],
        )

    @app.post("/notes", response_model=PageOut)
    def append_note(body: AppendNoteIn = Body(...)) -> PageOut:  # noqa: B008
        try:
            info = storage.append_note(
                content=body.content,
                rel_path=body.path,
                heading=body.heading,
            )
        except WriteLockTimeoutError as exc:
            raise HTTPException(
                status_code=503, detail=str(exc), headers={"Retry-After": "1"}
            ) from exc
        except InvalidPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except WikiStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return PageOut(
            path=info.path,
            title=info.title,
            size=info.size,
            modified=info.modified,
            extension=info.extension,
        )

    return app


app = create_app()

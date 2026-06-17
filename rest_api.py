"""API REST minimale per il wiki KISS.

Funziona da fallback al server MCP per i client che non supportano MCP.
Espone gli stessi cinque operatori di base su HTTP, più ``/health`` e
``/stats``. Avvio consigliato:

    uvicorn rest_api:app --host 127.0.0.1 --port 8765

La root del wiki è configurabile via variabile d'ambiente ``WIKI_ROOT`` o
argomento ``--root`` di Uvicorn (vedi ``create_app``).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query  # noqa: B008
from pydantic import BaseModel, Field

from wiki_core import (
    InvalidPathError,
    PageAlreadyExistsError,
    PageNotFoundError,
    WikiStorage,
    WikiStorageError,
)

DEFAULT_ROOT = Path(__file__).resolve().parent / "wiki"


# ----------------------------------------------------------------------
# Modelli Pydantic (definiti a livello di modulo per evitare forward
# reference non risolti).
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
    line: int = Field(..., description="Numero di riga, 1-based.")
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
# Factory dell'app
# ----------------------------------------------------------------------


def create_app(root: os.PathLike[str] | str | None = None) -> FastAPI:
    """Factory dell'app FastAPI."""
    wiki_root = (
        Path(root).expanduser().resolve()
        if root
        else Path(os.environ.get("WIKI_ROOT", DEFAULT_ROOT)).expanduser().resolve()
    )
    storage = WikiStorage(wiki_root)

    app = FastAPI(
        title="Wiki KISS API",
        version="0.1.0",
        description=(
            "Fallback HTTP per il wiki KISS. Specchia i tool MCP di base."
        ),
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "root": str(wiki_root)}

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
        q: str = Query(..., min_length=1, description="Testo da cercare."),  # noqa: B008
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

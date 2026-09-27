"""Modulo core per l'accesso al wiki su filesystem.

Espone l'oggetto :class:`WikiStorage` con tutte le primitive di lettura,
read, write, list and search. The module intentionally has no external
dependencies: it must remain usable even without the MCP server running.
"""

from .storage import (
    InvalidPathError,
    PageAlreadyExistsError,
    PageInfo,
    PageNotFoundError,
    SearchResult,
    WikiStorage,
    WikiStorageError,
    WriteLockTimeoutError,
)

__all__ = [
    "PageInfo",
    "SearchResult",
    "WikiStorage",
    "WikiStorageError",
    "WriteLockTimeoutError",
    "PageNotFoundError",
    "PageAlreadyExistsError",
    "InvalidPathError",
]

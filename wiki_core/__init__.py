"""Modulo core per l'accesso al wiki su filesystem.

Espone l'oggetto :class:`WikiStorage` con tutte le primitive di lettura,
scrittura, lista e ricerca. Il modulo è intenzionalmente privo di dipendenze
esterne: deve restare utilizzabile anche senza il server MCP attivo.
"""

from .storage import (
    InvalidPathError,
    PageAlreadyExistsError,
    PageInfo,
    PageNotFoundError,
    SearchResult,
    WikiStorage,
    WikiStorageError,
)

__all__ = [
    "PageInfo",
    "SearchResult",
    "WikiStorage",
    "WikiStorageError",
    "PageNotFoundError",
    "PageAlreadyExistsError",
    "InvalidPathError",
]

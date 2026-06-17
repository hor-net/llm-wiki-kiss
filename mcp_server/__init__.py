"""Server MCP per il wiki KISS.

Espone i cinque tool di base (``list_pages``, ``read_page``, ``search``,
``write_page``, ``append_note``) sopra lo storage definito in
:mod:`wiki_core`. Il trasporto predefinito è ``stdio``.
"""

from .server import build_server, main, run

__all__ = ["build_server", "main", "run"]

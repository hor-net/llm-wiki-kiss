"""Server MCP per il wiki KISS.

Esporta due trasporti:

* ``server`` — stdio (per client MCP locali: Claude Code, Claude Desktop,
  Open Cloud installato localmente, ...).
* ``http`` — Streamable HTTP (per client MCP in cloud che parlano il
  protocollo MCP 2025 via HTTPS, con autenticazione Bearer opzionale).
"""

from .server import build_server, main, run

__all__ = ["build_server", "main", "run"]

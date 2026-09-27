"""Smoke test del server MCP via stdio.

Avvia il server come sottoprocesso, esegue l'handshake MCP
(``initialize`` + ``notifications/initialized``) e invoca
``tools/list`` e ``tools/call`` per ciascuno dei 5 tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)


def send(process: subprocess.Popen, payload: dict) -> dict:
    line = json.dumps(payload)
    process.stdin.write(line + "\n")
    process.stdin.flush()
    out = process.stdout.readline()
    return json.loads(out)


def main() -> int:
    temporary_wiki = tempfile.TemporaryDirectory(prefix="wiki-kiss-smoke-")
    wiki = Path(temporary_wiki.name)
    (wiki / "notes").mkdir()
    (wiki / "index.md").write_text("# Index\n\nLocal MCP.\n", encoding="utf-8")

    cmd = [str(PYTHON), "-m", "mcp_server", "--root", str(wiki)]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        init = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0.1.0"},
                },
            },
        )
        assert "result" in init, init
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
            + "\n"
        )
        proc.stdin.flush()

        tools = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = {t["name"] for t in tools["result"]["tools"]}
        expected = {"list_pages", "read_page", "search", "write_page", "append_note"}
        assert expected <= tool_names, (tool_names, expected)
        print(f"Available tools: {sorted(tool_names)}")

        listing = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_pages", "arguments": {}},
            },
        )
        pages = json.loads(listing["result"]["content"][0]["text"])
        print(f"Pages found: {pages['count']}")

        read = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "read_page",
                    "arguments": {"path": "index.md"},
                },
            },
        )
        body = json.loads(read["result"]["content"][0]["text"])
        assert "Index" in body["content"], body
        print(f"Read {body['length']} characters of index.md")

        search = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {"query": "MCP", "max_results": 5},
                },
            },
        )
        results = json.loads(search["result"]["content"][0]["text"])
        print(f"Search results for 'MCP': {results['count']}")

        write = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "write_page",
                    "arguments": {
                        "path": "notes/smoke-test.md",
                        "content": "# Smoke\nCreato dal test.",
                        "overwrite": True,
                    },
                },
            },
        )
        info = json.loads(write["result"]["content"][0]["text"])
        print(f"Written: {info['path']} ({info['size']} bytes)")

        note = send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "append_note",
                    "arguments": {"content": "Voce di log smoke test."},
                },
            },
        )
        note_info = json.loads(note["result"]["content"][0]["text"])
        print(f"Log note: {note_info['path']}")

        print("ALL OK")
        return 0
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        temporary_wiki.cleanup()


if __name__ == "__main__":
    sys.exit(main())

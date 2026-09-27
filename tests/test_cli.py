"""Test della CLI locale offline."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from wiki_core.cli import main


@pytest.fixture()
def wiki(tmp_path: Path) -> Path:
    (tmp_path / "index.md").write_text("# Indice\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text(
        "# Nota A\nContiene MCP locale.\n", encoding="utf-8"
    )
    return tmp_path


def test_list_outputs_json(wiki: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(wiki), "list", "--subdir", "notes"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["pages"][0]["path"] == "notes/a.md"


def test_read_outputs_raw_markdown(wiki: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(wiki), "read", "notes/a.md"]) == 0
    assert capsys.readouterr().out == "# Nota A\nContiene MCP locale.\n"


def test_search_outputs_json(wiki: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(wiki), "search", "mcp"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["results"][0]["path"] == "notes/a.md"


def test_write_and_no_overwrite(wiki: Path, capsys: pytest.CaptureFixture[str]) -> None:
    command = [
        "--root", str(wiki), "write", "notes/new.md", "--content", "# New\nOffline"
    ]
    assert main(command) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == "notes/new.md"
    assert (wiki / "notes" / "new.md").read_text(encoding="utf-8") == "# New\nOffline"

    assert main([*command, "--no-overwrite"]) == 1
    assert "esiste già" in capsys.readouterr().err


def test_append_reads_stdin(
    wiki: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("Nota da stdin"))
    assert main(["--root", str(wiki), "append", "notes/a.md"]) == 0
    capsys.readouterr()
    assert "Nota da stdin" in (wiki / "notes" / "a.md").read_text(encoding="utf-8")


def test_stats_uses_wiki_root_environment(
    wiki: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("WIKI_ROOT", str(wiki))
    assert main(["stats"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pages"] >= 2
    assert "root" not in payload


def test_rebuild_indexes(wiki: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(wiki), "rebuild-indexes"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ok"}
    assert "[Nota A](a.md)" in (wiki / "notes" / "index.md").read_text(
        encoding="utf-8"
    )

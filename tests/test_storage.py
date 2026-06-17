"""Test per il modulo wiki_core.storage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wiki_core import (  # noqa: E402
    InvalidPathError,
    PageAlreadyExistsError,
    PageNotFoundError,
    WikiStorage,
    WikiStorageError,
)


@pytest.fixture()
def tmp_wiki(tmp_path: Path) -> WikiStorage:
    (tmp_path / "index.md").write_text("# Indice\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text(
        "# Nota A\nMCP è uno standard.\nAltro testo.\n",
        encoding="utf-8",
    )
    (tmp_path / "notes" / "b.md").write_text(
        "# Nota B\nNessuna menzione.\n",
        encoding="utf-8",
    )
    (tmp_path / "decisions").mkdir()
    (tmp_path / "decisions" / "0001.md").write_text(
        "# ADR 0001\nScelto MCP.\n",
        encoding="utf-8",
    )
    return WikiStorage(tmp_path)


def test_list_pages(tmp_wiki: WikiStorage) -> None:
    pages = tmp_wiki.list_pages()
    paths = {p.path for p in pages}
    assert "index.md" in paths
    assert "notes/a.md" in paths
    assert "decisions/0001.md" in paths
    assert all(p.extension == ".md" for p in pages)


def test_list_pages_subdir(tmp_wiki: WikiStorage) -> None:
    pages = tmp_wiki.list_pages(subdir="notes")
    paths = {p.path for p in pages}
    assert paths == {"notes/a.md", "notes/b.md"}


def test_read_page(tmp_wiki: WikiStorage) -> None:
    content = tmp_wiki.read_page("notes/a.md")
    assert "MCP" in content


def test_read_page_missing(tmp_wiki: WikiStorage) -> None:
    with pytest.raises(PageNotFoundError):
        tmp_wiki.read_page("notes/inesistente.md")


def test_path_traversal_blocked(tmp_wiki: WikiStorage) -> None:
    with pytest.raises(InvalidPathError):
        tmp_wiki.read_page("../etc/passwd")
    with pytest.raises(InvalidPathError):
        tmp_wiki.read_page("notes/../../../etc/passwd")


def test_write_page_creates(tmp_wiki: WikiStorage) -> None:
    info = tmp_wiki.write_page(
        "notes/nuova.md", "# Nuova\nContenuto.", overwrite=True
    )
    assert info.path == "notes/nuova.md"
    assert tmp_wiki.page_exists("notes/nuova.md")


def test_write_page_extension_added(tmp_wiki: WikiStorage) -> None:
    info = tmp_wiki.write_page("notes/auto", "# Auto", overwrite=True)
    assert info.path == "notes/auto.md"


def test_write_page_no_overwrite(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.write_page("notes/x.md", "x", overwrite=True)
    with pytest.raises(PageAlreadyExistsError):
        tmp_wiki.write_page("notes/x.md", "y", overwrite=False)


def test_append_note_default_log(tmp_wiki: WikiStorage) -> None:
    info = tmp_wiki.append_note(content="Prima nota di log.")
    assert info.path.startswith("logs/")
    assert info.path.endswith(".md")
    second = tmp_wiki.append_note(content="Seconda nota.")
    assert second.path == info.path
    content = tmp_wiki.read_page(info.path)
    assert "Prima nota di log." in content
    assert "Seconda nota." in content


def test_append_note_with_heading(tmp_wiki: WikiStorage) -> None:
    info = tmp_wiki.append_note(
        rel_path="notes/append.md",
        content="entry",
        heading="Update",
    )
    content = tmp_wiki.read_page(info.path)
    assert "## Update" in content


def test_search_case_insensitive(tmp_wiki: WikiStorage) -> None:
    results = tmp_wiki.search(query="mcp")
    paths = {r.path for r in results}
    assert "notes/a.md" in paths
    assert "decisions/0001.md" in paths


def test_search_max_results(tmp_wiki: WikiStorage) -> None:
    results = tmp_wiki.search(query="MCP", max_results=1)
    assert len(results) == 1


def test_search_empty_query(tmp_wiki: WikiStorage) -> None:
    assert tmp_wiki.search(query="") == []
    assert tmp_wiki.search(query="   ") == []


def test_search_in_subdir(tmp_wiki: WikiStorage) -> None:
    results = tmp_wiki.search(query="MCP", subdir="notes")
    paths = {r.path for r in results}
    assert "decisions/0001.md" not in paths
    assert "notes/a.md" in paths


def test_invalid_path_control_chars(tmp_wiki: WikiStorage) -> None:
    with pytest.raises(InvalidPathError):
        tmp_wiki.read_page("notes/a\nb.md")


def test_stats(tmp_wiki: WikiStorage) -> None:
    stats = tmp_wiki.stats()
    assert stats["pages"] >= 4
    assert ".md" in stats["extensions"]


def test_wiki_storage_requires_existing_root(tmp_path: Path) -> None:
    with pytest.raises(WikiStorageError):
        WikiStorage(tmp_path / "non-esistente")

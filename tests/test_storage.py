"""Test per il modulo wiki_core.storage."""

from __future__ import annotations

import multiprocessing
import os
import sys
from concurrent.futures import ThreadPoolExecutor
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
    WriteLockTimeoutError,
)


def _append_from_process(root: str, marker: str) -> None:
    WikiStorage(root).append_note(marker, rel_path="logs/concurrent.md")


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
    assert "root" not in stats


def test_wiki_storage_requires_existing_root(tmp_path: Path) -> None:
    with pytest.raises(WikiStorageError):
        WikiStorage(tmp_path / "non-esistente")


def test_write_page_updates_category_and_general_indexes(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.write_page("notes/nuova-pagina.md", "# Pagina nuova\nTesto")

    category_index = tmp_wiki.read_page("notes/index.md")
    general_index = tmp_wiki.read_page("index.md")

    assert "[Pagina nuova](nuova-pagina.md)" in category_index
    assert "[notes](notes/index.md)" in general_index


def test_write_page_new_category_updates_general_index(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.write_page("ricette/pasta.md", "# Pasta")

    assert "[ricette](ricette/index.md)" in tmp_wiki.read_page("index.md")
    assert "[Pasta](pasta.md)" in tmp_wiki.read_page("ricette/index.md")


def test_append_note_updates_indexes(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.append_note(
        rel_path="notes/aggiunta.md", content="Nota aggiunta", heading="Aggiornamento"
    )

    assert "[aggiunta](aggiunta.md)" in tmp_wiki.read_page("notes/index.md")
    assert "[notes](notes/index.md)" in tmp_wiki.read_page("index.md")


def test_indexes_include_nested_pages_with_relative_links(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.write_page("projects/roadmap/q3.md", "# Roadmap Q3")

    index = tmp_wiki.read_page("projects/index.md")
    assert "[Roadmap Q3](roadmap/q3.md)" in index
    assert "[projects](projects/index.md)" not in index


def test_rebuilding_indexes_is_idempotent(tmp_wiki: WikiStorage) -> None:
    tmp_wiki.write_page("notes/one.md", "# One")
    first_general = tmp_wiki.read_page("index.md")
    first_category = tmp_wiki.read_page("notes/index.md")

    tmp_wiki.rebuild_indexes()

    assert tmp_wiki.read_page("index.md") == first_general
    assert tmp_wiki.read_page("notes/index.md") == first_category


def test_concurrent_thread_appends_are_not_lost(tmp_wiki: WikiStorage) -> None:
    markers = [f"[thread-{index:02d}]" for index in range(12)]
    storages = [WikiStorage(tmp_wiki.root) for _ in markers]

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(
            lambda item: item[0].append_note(item[1], rel_path="logs/threads.md"),
            zip(storages, markers, strict=True),
        ))

    content = tmp_wiki.read_page("logs/threads.md")
    for marker in markers:
        assert content.count(marker) == 1


def test_concurrent_process_appends_are_not_lost(tmp_wiki: WikiStorage) -> None:
    context = multiprocessing.get_context("spawn")
    markers = [f"[process-{index:02d}]" for index in range(4)]
    processes = [
        context.Process(target=_append_from_process, args=(str(tmp_wiki.root), marker))
        for marker in markers
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    content = tmp_wiki.read_page("logs/concurrent.md")
    for marker in markers:
        assert content.count(marker) == 1


@pytest.mark.skipif(os.name == "nt", reason="Il test usa direttamente flock.")
def test_write_lock_times_out_when_another_process_owns_it(tmp_wiki: WikiStorage) -> None:
    import fcntl

    lock_path = tmp_wiki.root / ".wiki-kiss.lock"
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        contender = WikiStorage(tmp_wiki.root, write_lock_timeout=0.02)
        with pytest.raises(WriteLockTimeoutError):
            contender.write_page("notes/blocked.md", "# Blocked")

    assert not tmp_wiki.page_exists("notes/blocked.md")

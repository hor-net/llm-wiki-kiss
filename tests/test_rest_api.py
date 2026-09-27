"""Test per l'API REST."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rest_api import create_app  # noqa: E402

TOKEN = "rest-test-token-12345"


@pytest.fixture()
def app(tmp_path: Path):
    (tmp_path / "index.md").write_text("# Indice\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text(
        "# Nota A\nContiene MCP e basta.\n", encoding="utf-8"
    )
    return create_app(root=tmp_path, token=TOKEN)


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


def test_health(client: TestClient, tmp_path: Path) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert res.headers["cache-control"] == "no-store"
    assert "root" not in data
    assert str(tmp_path) not in res.text


def test_rest_requires_bearer_token(app) -> None:
    unauthenticated = TestClient(app)
    assert unauthenticated.get("/health").status_code == 200
    assert unauthenticated.get("/pages").status_code == 401
    assert unauthenticated.get("/docs").status_code == 401
    assert unauthenticated.get(
        "/pages", headers={"Authorization": "Bearer wrong"}
    ).status_code == 403


def test_rest_without_configured_token_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WIKI_MCP_TOKEN", raising=False)
    (tmp_path / "index.md").write_text("# Indice\n", encoding="utf-8")
    application = create_app(root=tmp_path, token=None)
    assert TestClient(application).get("/health").status_code == 503


def test_list_pages(client: TestClient) -> None:
    res = client.get("/pages")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    data = res.json()
    assert data["count"] >= 2
    paths = {p["path"] for p in data["pages"]}
    assert "index.md" in paths


def test_read_page(client: TestClient) -> None:
    res = client.get("/pages/notes/a.md")
    assert res.status_code == 200
    data = res.json()
    assert "MCP" in data["content"]


def test_read_page_missing(client: TestClient) -> None:
    res = client.get("/pages/notes/inesistente.md")
    assert res.status_code == 404


def test_write_and_read_roundtrip(client: TestClient) -> None:
    res = client.put(
        "/pages/notes/nuova.md", json={"content": "# Nuova\nCiao."}
    )
    assert res.status_code == 200
    read = client.get("/pages/notes/nuova.md")
    assert read.status_code == 200
    assert "Ciao" in read.json()["content"]


def test_write_conflict(client: TestClient) -> None:
    res = client.put(
        "/pages/notes/a.md",
        json={"content": "# Sovrascrittura", "overwrite": False},
    )
    assert res.status_code == 409


def test_search(client: TestClient) -> None:
    res = client.get("/search", params={"q": "MCP"})
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    assert data["results"][0]["path"].endswith("a.md")


def test_append_note_default(client: TestClient) -> None:
    res = client.post(
        "/notes", json={"content": "Voce di log di test."}
    )
    assert res.status_code == 200
    path = res.json()["path"]
    read = client.get(f"/pages/{path}")
    assert read.status_code == 200
    assert "Voce di log di test." in read.json()["content"]


def test_stats(client: TestClient) -> None:
    res = client.get("/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["pages"] >= 2

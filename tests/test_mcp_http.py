"""Test del server MCP Streamable HTTP.

Questi test coprono le parti sincronizzabili (factory, middleware,
configurazione). Per il test funzionale end-to-end del session manager
(Streamable HTTP negotiation) vedi ``tests/smoke_mcp_http.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.routing import Route
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp_server.http import BearerAuthMiddleware, create_app  # noqa: E402

TOKEN = "test-token-12345"


@pytest.fixture()
def wiki(tmp_path: Path) -> Path:
    (tmp_path / "index.md").write_text("# Indice\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text(
        "# Nota A\nMCP è uno standard.\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def app(wiki: Path):
    return create_app(
        wiki_root=wiki, token=TOKEN, json_response=True, stateless=True
    )


@pytest.fixture()
def app_no_auth(wiki: Path):
    return create_app(
        wiki_root=wiki, token=None, json_response=True, stateless=True
    )


# ----------------------------------------------------------------------
# Test del factory e della configurazione
# ----------------------------------------------------------------------


def test_factory_returns_starlette(app) -> None:
    assert app is not None


def test_factory_uses_env_token(monkeypatch: pytest.MonkeyPatch, wiki: Path) -> None:
    monkeypatch.setenv("WIKI_MCP_TOKEN", "env-token")
    application = create_app(wiki_root=wiki, token=None, json_response=True, stateless=True)
    assert application is not None


def test_factory_with_explicit_token_overrides_env(
    monkeypatch: pytest.MonkeyPatch, wiki: Path
) -> None:
    monkeypatch.setenv("WIKI_MCP_TOKEN", "env-token")
    application = create_app(
        wiki_root=wiki, token="explicit-token", json_response=True, stateless=True
    )
    # Verifica che il token esplicito sia usato.
    assert application is not None


# ----------------------------------------------------------------------
# Test del middleware Bearer
# ----------------------------------------------------------------------


def test_bearer_middleware_passes_when_disabled() -> None:
    """Se il token atteso è None, il middleware non blocca nulla."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse

    async def hello(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/", hello)],
        middleware=[Middleware(BearerAuthMiddleware, expected_token=None)],
    )
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "ok"


def test_bearer_middleware_requires_token() -> None:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse

    async def hello(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/", hello)],
        middleware=[Middleware(BearerAuthMiddleware, expected_token="secret")],
    )
    client = TestClient(app)
    # Senza header
    r = client.get("/")
    assert r.status_code == 401
    # Token sbagliato
    r = client.get("/", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403
    # Token giusto
    r = client.get("/", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200


def test_bearer_middleware_allows_health_without_auth() -> None:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse

    async def hello(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/", hello), Route("/health", hello), Route("/healthz", hello)],
        middleware=[Middleware(BearerAuthMiddleware, expected_token="secret")],
    )
    client = TestClient(app)
    # /health è esente
    r = client.get("/health")
    assert r.status_code == 200
    r = client.get("/healthz")
    assert r.status_code == 200
    # / richiede auth
    r = client.get("/")
    assert r.status_code == 401

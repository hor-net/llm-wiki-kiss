"""MCP OAuth discovery and authorization with locally signed Auth0-style JWTs."""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from mcp_server.http import create_app
from mcp_server.oauth import METADATA_PREFIX, READ_SCOPE

ISSUER = "https://tenant.example/"
RESOURCE = "https://wiki.example/mcp"
CLIENT_ID = "gemini-test-client"
KEY_ID = "test-signing-key"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def client(tmp_path, monkeypatch, signing_key):
    (tmp_path / "index.md").write_text("# Test wiki\n", encoding="utf-8")
    monkeypatch.setenv("WIKI_MCP_AUTH_MODE", "oauth")
    monkeypatch.setenv("WIKI_MCP_OAUTH_ISSUER", ISSUER.rstrip("/"))
    monkeypatch.setenv("WIKI_MCP_OAUTH_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("WIKI_MCP_URL", RESOURCE)
    key = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    jwks = jwt.PyJWKSet.from_dict({"keys": [{**key, "kid": KEY_ID}]})

    def get_jwk_set(self, refresh=False):
        assert self.uri == ISSUER + ".well-known/jwks.json"
        assert not refresh
        return jwks

    monkeypatch.setattr(jwt.PyJWKClient, "get_jwk_set", get_jwk_set)
    with TestClient(create_app(wiki_root=tmp_path, token="legacy-secret")) as client:
        yield client


def _token(signing_key, *, kid=KEY_ID, **override):
    claims = {
        "iss": ISSUER, "aud": RESOURCE, "exp": int(time.time()) + 60,
        "sub": "auth0|test-user", "azp": CLIENT_ID, "scope": READ_SCOPE, **override,
    }
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": kid})


def _rpc(client, token, method, params=None):
    return client.post(
        "/mcp", follow_redirects=False,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"},
    )


def test_discovery_and_no_static_fallback(client):
    response = client.post("/mcp")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert f'resource_metadata="https://wiki.example{METADATA_PREFIX}/mcp"' in response.headers["WWW-Authenticate"]
    assert f'scope="{READ_SCOPE}"' in response.headers["WWW-Authenticate"]
    for path in (METADATA_PREFIX + "/mcp", METADATA_PREFIX):
        metadata = client.get(path)
        assert metadata.status_code == 200
        assert metadata.headers["cache-control"] == "no-store"
        assert metadata.json() == {
            "resource": RESOURCE, "authorization_servers": [ISSUER],
            "scopes_supported": [READ_SCOPE], "bearer_methods_supported": ["header"],
        }
    assert client.get("/health").status_code == 200
    assert _rpc(client, "legacy-secret", "tools/list").status_code == 401
    assert client.get("/").status_code == 401


def test_real_mcp_rpc_is_read_only(client, signing_key, tmp_path):
    token = _token(signing_key, aud=[RESOURCE, "https://tenant.example/userinfo"])
    result = _rpc(client, token, "initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"},
    })
    assert result.status_code == 200
    assert "prompts" not in result.json()["result"]["capabilities"]
    listed = _rpc(client, token, "tools/list")
    assert listed.status_code == 200
    assert {tool["name"] for tool in listed.json()["result"]["tools"]} == {"list_pages", "read_page", "search"}
    result = _rpc(client, token, "tools/call", {"name": "read_page", "arguments": {"path": "index.md"}})
    assert result.status_code == 200
    assert "# Test wiki" in result.json()["result"]["content"][0]["text"]
    for name in ("write_page", "append_note"):
        blocked = _rpc(client, token, "tools/call", {
            "name": name, "arguments": {"path": "test.md", "content": "blocked"},
        })
        assert blocked.json()["result"]["isError"]
    assert {p.name for p in tmp_path.iterdir()} == {"index.md"}


@pytest.mark.parametrize("claims", [
    {"iss": "https://untrusted.example/"}, {"aud": "https://other.example/mcp"},
    {"azp": "different-client"}, {"sub": ""}, {"exp": 1}, {"exp": None},
    {"gty": "client-credentials"}, {"kid": "unknown"},
])
def test_invalid_jwt_claims_are_rejected(client, signing_key, claims):
    response = _rpc(client, _token(signing_key, **claims), "tools/list")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["WWW-Authenticate"]


def test_untrusted_signatures_are_rejected(client):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert _rpc(client, _token(other_key), "tools/list").status_code == 401


@pytest.mark.parametrize("scope", ["", "wiki:read-all", None, [READ_SCOPE]])
def test_read_scope_is_required(client, signing_key, scope):
    response = _rpc(client, _token(signing_key, scope=scope), "tools/list")
    assert response.status_code == 403
    assert 'error="insufficient_scope"' in response.headers["WWW-Authenticate"]


def test_no_jwks_fails_closed(client, signing_key, monkeypatch):
    def unavailable(*args, **kwargs):
        raise jwt.exceptions.PyJWKClientConnectionError("offline")

    monkeypatch.setattr(jwt.PyJWKClient, "get_jwk_set", unavailable)
    assert _rpc(client, _token(signing_key), "tools/list").status_code == 503


@pytest.mark.parametrize("override", [
    {"WIKI_MCP_AUTH_MODE": "invalid"}, {"WIKI_MCP_OAUTH_ISSUER": "http://tenant.example/"},
    {"WIKI_MCP_URL": "https://wiki.example/not-mcp"}, {"WIKI_MCP_OAUTH_CLIENT_ID": ""},
])
def test_invalid_configuration_does_not_fall_back_to_bearer(tmp_path, monkeypatch, override):
    env = {
        "WIKI_MCP_AUTH_MODE": "oauth", "WIKI_MCP_OAUTH_ISSUER": ISSUER,
        "WIKI_MCP_URL": RESOURCE, "WIKI_MCP_OAUTH_CLIENT_ID": CLIENT_ID, **override,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        create_app(wiki_root=tmp_path, token="legacy-secret")

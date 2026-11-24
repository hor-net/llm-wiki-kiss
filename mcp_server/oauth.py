"""Read-only MCP OAuth resource server for Auth0 JWT access tokens."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

import anyio
import jwt
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import no_store_sender

READ_SCOPE = "wiki:read"
METADATA_PREFIX = "/.well-known/oauth-protected-resource"


def _https_url(value: str) -> SplitResult:
    if not re.fullmatch(r"https://[A-Za-z0-9.\-:\[\]/_~]+", value):
        raise ValueError("OAuth requires an HTTPS URL without credentials, query or fragment")
    url = urlsplit(value)
    if not url.hostname or url.port == 0:
        raise ValueError("Invalid OAuth URL host or port")
    return url


@dataclass(frozen=True)
class OAuthSettings:
    issuer: str
    resource: str
    client_id: str

    @classmethod
    def from_env(cls, mcp_path: str) -> OAuthSettings | None:
        mode = os.environ.get("WIKI_MCP_AUTH_MODE", "bearer")
        if mode == "bearer":
            return None
        if mode != "oauth":
            raise ValueError("WIKI_MCP_AUTH_MODE must be bearer or oauth")
        issuer = os.environ.get("WIKI_MCP_OAUTH_ISSUER", "").strip()
        resource = os.environ.get("WIKI_MCP_URL", "").strip()
        client_id = os.environ.get("WIKI_MCP_OAUTH_CLIENT_ID", "").strip()
        if not all((issuer, resource, client_id)):
            raise ValueError("OAuth requires WIKI_MCP_OAUTH_ISSUER, WIKI_MCP_URL and WIKI_MCP_OAUTH_CLIENT_ID")
        if _https_url(issuer).path not in ("", "/"):
            raise ValueError("WIKI_MCP_OAUTH_ISSUER must be an HTTPS origin")
        endpoint = mcp_path.rstrip("/")
        if not endpoint or _https_url(resource).path not in {endpoint, endpoint + "/"}:
            raise ValueError("WIKI_MCP_URL must match the MCP endpoint path")
        return cls(issuer.rstrip("/") + "/", resource, client_id)

    @property
    def metadata_path(self) -> str:
        return METADATA_PREFIX + urlsplit(self.resource).path

    @property
    def metadata_url(self) -> str:
        return f"https://{urlsplit(self.resource).netloc}{self.metadata_path}"

    def metadata(self) -> dict:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [READ_SCOPE],
        }


class OAuthMiddleware:
    def __init__(self, app: ASGIApp, settings: OAuthSettings) -> None:
        self.app = app
        self.settings = settings
        self.public_paths = {"/health", "/healthz", METADATA_PREFIX, settings.metadata_path}
        self.keys = jwt.PyJWKClient(settings.issuer + ".well-known/jwks.json", timeout=5)
        self.challenge = f'Bearer resource_metadata="{settings.metadata_url}", scope="{READ_SCOPE}"'

    def _claims(self, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise jwt.InvalidTokenError("Expected RS256 and a key ID")
        # Don't force network refreshes based on an untrusted key ID. The
        # cached JWKS expires on its own (five minutes by default).
        key = next((k for k in self.keys.get_signing_keys() if k.key_id == header["kid"]), None)
        if key is None:
            raise jwt.InvalidTokenError("Unknown signing key")
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], audience=self.settings.resource,
            issuer=self.settings.issuer, options={"require": ["iss", "aud", "exp", "sub", "azp"]},
        )
        if (
            claims["azp"] != self.settings.client_id
            or not isinstance(claims["sub"], str)
            or not claims["sub"]
            or claims.get("gty") == "client-credentials"
        ):
            raise jwt.InvalidTokenError("Expected a user token issued to the configured client")
        return claims

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        send = no_store_sender(send)
        if scope["path"] in self.public_paths and scope["method"] in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope).getlist("authorization")
        match = re.fullmatch(r"Bearer ([A-Za-z0-9._-]+)", headers[0], re.IGNORECASE) if len(headers) == 1 else None
        if not match:
            await self._reject(scope, receive, send, 401, "invalid_token" if headers else None)
            return
        try:
            claims = await anyio.to_thread.run_sync(self._claims, match[1])
        except PyJWKClientConnectionError:
            await self._reject(scope, receive, send, 503, "temporarily_unavailable")
            return
        except (PyJWTError, TypeError, ValueError, OverflowError):
            await self._reject(scope, receive, send, 401, "invalid_token")
            return
        scopes = claims.get("scope")
        if not isinstance(scopes, str) or READ_SCOPE not in scopes.split():
            await self._reject(scope, receive, send, 403, "insufficient_scope")
            return
        await self.app(scope, receive, send)

    async def _reject(
        self, scope: Scope, receive: Receive, send: Send, status: int, error: str | None
    ) -> None:
        headers = {}
        if status in (401, 403):
            challenge = self.challenge + (f', error="{error}"' if error else "")
            headers["WWW-Authenticate"] = challenge
        await JSONResponse(
            {"error": error or "missing_bearer_token"}, status_code=status, headers=headers
        )(scope, receive, send)

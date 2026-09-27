"""Autenticazione Bearer condivisa dai trasporti HTTP del wiki."""

from __future__ import annotations

import hmac
import json
from collections.abc import Collection

from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuthMiddleware:
    """Protegge un'app ASGI con un singolo Bearer token.

    Se il token non è configurato il middleware resta *fail closed* e risponde
    503 a ogni richiesta. Gli health check possono essere pubblici solo dopo
    che il servizio è stato configurato con un token.
    """

    def __init__(
        self,
        app: ASGIApp,
        expected_token: str | None,
        exempt_paths: Collection[str] = ("/health", "/healthz"),
    ) -> None:
        self.app = app
        self.expected_token = (expected_token or "").strip() or None
        self.exempt_paths = frozenset(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.expected_token is None:
            await self._reject(send, 503, "access_token_not_configured")
            return

        path = scope.get("path", "")
        if path in self.exempt_paths:
            await self.app(scope, receive, self._no_store_sender(send))
            return

        headers = dict(scope.get("headers") or [])
        authorization = headers.get(b"authorization", b"").decode(
            "latin-1", errors="replace"
        )
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            await self._reject(send, 401, "missing_bearer_token")
            return
        if not hmac.compare_digest(token.strip(), self.expected_token):
            await self._reject(send, 403, "invalid_bearer_token")
            return

        await self.app(scope, receive, self._no_store_sender(send))

    @staticmethod
    def _no_store_sender(send: Send):
        async def send_with_headers(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.extend([
                    (b"cache-control", b"no-store"),
                    (b"pragma", b"no-cache"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-content-type-options", b"nosniff"),
                ])
                message = {**message, "headers": headers}
            await send(message)

        return send_with_headers

    @staticmethod
    async def _reject(send: Send, status: int, error: str) -> None:
        body = json.dumps({"error": error}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"pragma", b"no-cache"),
            (b"referrer-policy", b"no-referrer"),
            (b"x-content-type-options", b"nosniff"),
        ]
        if status in (401, 403):
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body, "more_body": False})

"""HTTP middleware shared by API routes."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.core.errors import error_response

MAX_MUTATION_BODY_BYTES = 1_048_576


class RequestBodyLimitMiddleware:
    """Enforce the request body limit for POST and PATCH before routing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PATCH"}:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > MAX_MUTATION_BODY_BYTES:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        body = bytearray()
        messages: list[Message] = []
        too_large = False
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                body.extend(message.get("body", b""))
                if len(body) > MAX_MUTATION_BODY_BYTES:
                    too_large = True
                    break
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        if too_large:
            await self._reject(scope, receive, send)
            return

        async def replay_receive() -> Message:
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            413, "PAYLOAD_TOO_LARGE", "Request body exceeds 1 MB"
        )
        await response(scope, receive, send)

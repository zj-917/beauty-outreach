"""ASGI middleware for request ids and admin authentication."""

from __future__ import annotations

import logging
import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.logging import request_id_var
from app.core.security import verify_admin_token

logger = logging.getLogger(__name__)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_WEBHOOK_PREFIX = "/api/v1/webhooks/"


class RequestContextMiddleware:
    """Attach a validated request id to logs and the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        status = {"code": 0}

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        method = scope.get("method", "")
        path = scope.get("path", "")
        logger.info("request.start method=%s path=%s request_id=%s", method, path, request_id)
        try:
            await self.app(scope, receive, send_with_header)
        except Exception:
            status["code"] = status["code"] or 500
            raise
        finally:
            logger.info(
                "request.end method=%s path=%s status=%s request_id=%s",
                method,
                path,
                status["code"],
                request_id,
            )
            request_id_var.reset(token)


class AdminAuthMiddleware:
    """Require X-Admin-Token on /api/v1 routes, except signed webhooks."""

    def __init__(self, app: ASGIApp, admin_token: str) -> None:
        self.app = app
        self.admin_token = admin_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        protected = path == "/api/v1" or path.startswith("/api/v1/")
        if protected and not path.startswith(_WEBHOOK_PREFIX):
            provided = Headers(scope=scope).get("x-admin-token")
            if not verify_admin_token(provided, self.admin_token):
                response = JSONResponse(
                    error_body(
                        "UNAUTHORIZED",
                        "Invalid or missing admin token",
                        request_id_var.get(),
                    ),
                    status_code=401,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

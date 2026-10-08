import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import HTTP_DURATION, HTTP_IN_PROGRESS, HTTP_REQUESTS
from app.core.request_context import request_id_var

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_QUIET_PATHS = frozenset({"/health", "/ready", "/metrics"})


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        started = time.perf_counter()
        HTTP_IN_PROGRESS.inc()
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("unhandled error", extra={"method": scope["method"], "path": scope["path"]})
            if not response_started:
                response = JSONResponse(
                    {"detail": "Internal server error", "request_id": request_id},
                    status_code=500,
                    headers={REQUEST_ID_HEADER: request_id},
                )
                status_code = 500
                await response(scope, receive, send)
        finally:
            HTTP_IN_PROGRESS.dec()
            duration = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method = scope["method"]
            HTTP_REQUESTS.labels(method, route, str(status_code)).inc()
            HTTP_DURATION.labels(method, route).observe(duration)
            self._log_access(scope, route, status_code, duration)
            request_id_var.reset(token)

    @staticmethod
    def _log_access(scope: Scope, route: str, status_code: int, duration: float) -> None:
        duration_ms = round(duration * 1000, 2)
        level = logging.DEBUG if scope["path"] in _QUIET_PATHS else logging.INFO
        logger.log(
            level,
            "%s %s -> %s (%.1f ms)",
            scope["method"],
            scope["path"],
            status_code,
            duration_ms,
            extra={
                "method": scope["method"],
                "path": scope["path"],
                "route": route,
                "status": status_code,
                "duration_ms": duration_ms,
            },
        )

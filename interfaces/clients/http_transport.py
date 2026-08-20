"""Shared backend HTTP transport for PyQt/CLI clients (J04-M0-P0)."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable
from urllib.parse import urlparse


class BackendTransportError(RuntimeError):
    """Transport-level failure talking to the backend."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class BackendHttpTransport:
    """Single owner for base URL, auth header, request-id, JSON/binary, timeouts."""

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: Callable[[], str | None] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = validate_backend_base_url(base_url)
        self._token_provider = token_provider
        self._timeout_seconds = timeout_seconds

    @property
    def base_url(self) -> str:
        return self._base_url

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
        auth: bool = True,
        expect_json: bool = True,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        request_headers = {"X-Request-ID": f"qmtool-{uuid.uuid4()}"}
        if headers:
            request_headers.update(headers)
        if auth:
            token = ""
            if self._token_provider is not None:
                token = (self._token_provider() or "").strip()
            if not token:
                raise BackendTransportError("backend session token is required", status_code=401)
            request_headers["Authorization"] = f"Bearer {token}"
        data: bytes | None = None
        if raw_body is not None:
            data = raw_body
            request_headers["Content-Type"] = content_type
        elif body is not None:
            data = json.dumps(body, ensure_ascii=True).encode("utf-8")
            request_headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                payload = resp.read()
                if not expect_json:
                    return payload
                if not payload:
                    return None
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            # Never include Authorization material; detail is server JSON only.
            raise BackendTransportError(
                f"backend HTTP {exc.code}: {detail}",
                status_code=exc.code,
                body=detail,
            ) from None
        except urllib.error.URLError as exc:
            raise BackendTransportError(
                f"backend unreachable at {self._base_url}: {exc.reason}"
            ) from None

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        raw_body: bytes | None = None,
        content_type: str = "application/octet-stream",
        auth: bool = True,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """Return an opaque response body together with response headers."""
        url = f"{self._base_url}{path}"
        request_headers = {"X-Request-ID": f"qmtool-{uuid.uuid4()}"}
        if headers:
            request_headers.update(headers)
        if auth:
            token = (self._token_provider() or "").strip() if self._token_provider is not None else ""
            if not token:
                raise BackendTransportError("backend session token is required", status_code=401)
            request_headers["Authorization"] = f"Bearer {token}"
        if raw_body is not None:
            request_headers["Content-Type"] = content_type
        req = urllib.request.Request(
            url,
            data=raw_body,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                return resp.read(), {str(key): str(value) for key, value in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BackendTransportError(
                f"backend HTTP {exc.code}: {detail}",
                status_code=exc.code,
                body=detail,
            ) from None
        except urllib.error.URLError as exc:
            raise BackendTransportError(
                f"backend unreachable at {self._base_url}: {exc.reason}"
            ) from None


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def validate_backend_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        raise BackendTransportError("QMTOOL_BACKEND_URL is empty")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise BackendTransportError("QMTOOL_BACKEND_URL must use http or https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise BackendTransportError("QMTOOL_BACKEND_URL host is missing")
    if parsed.scheme == "http" and host not in _LOOPBACK_HOSTS:
        raise BackendTransportError(
            "QMTOOL_BACKEND_URL must use https for non-loopback hosts"
        )
    return value


def resolve_backend_base_url_from_env() -> str:
    return validate_backend_base_url(os.environ.get("QMTOOL_BACKEND_URL", "http://127.0.0.1:8000"))


def error_code_from_body(body: str) -> str | None:
    try:
        payload = json.loads(body)
    except Exception:
        return None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        err = detail.get("error")
        return str(err) if err is not None else None
    return None

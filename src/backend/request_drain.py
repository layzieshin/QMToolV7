"""Backend request admission and in-flight state-change draining.

The tracker is process-local transport lifecycle state. It deliberately wraps
the actual FastAPI endpoint callable so synchronous handlers remain counted in
their AnyIO worker thread even when the surrounding ASGI task is cancelled.
"""
from __future__ import annotations

import inspect
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.routing import APIRoute


STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_APP_STATE_ATTRIBUTE = "request_drain_tracker"
_WRAPPED_ATTRIBUTE = "__qmtool_request_drain_wrapped__"


class RequestDrainPhase(str, Enum):
    ACCEPTING = "accepting"
    DRAINING = "draining"


class RequestDrainRejected(RuntimeError):
    """Raised when a state-changing execution starts after drain began."""


class RequestDrainTracker:
    """Atomically admit state changes and wait for admitted work to finish."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._phase = RequestDrainPhase.ACCEPTING
        self._active = 0

    @property
    def phase(self) -> RequestDrainPhase:
        with self._condition:
            return self._phase

    @property
    def active_count(self) -> int:
        with self._condition:
            return self._active

    def enter(self) -> None:
        with self._condition:
            if self._phase is RequestDrainPhase.DRAINING:
                raise RequestDrainRejected("backend host is stopping")
            self._active += 1

    def leave(self) -> None:
        with self._condition:
            if self._active <= 0:
                raise RuntimeError("request drain tracker active count underflow")
            self._active -= 1
            if self._active == 0:
                self._condition.notify_all()

    def begin_drain(self) -> None:
        with self._condition:
            self._phase = RequestDrainPhase.DRAINING
            if self._active == 0:
                self._condition.notify_all()

    def wait_until_idle(self, *, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self._active == 0,
                timeout=max(0.0, timeout),
            )


def ensure_request_drain_tracker(app: FastAPI) -> RequestDrainTracker:
    """Return the app tracker, installing exactly one when absent."""
    existing = getattr(app.state, _APP_STATE_ATTRIBUTE, None)
    if existing is None:
        existing = RequestDrainTracker()
        setattr(app.state, _APP_STATE_ATTRIBUTE, existing)
    if not isinstance(existing, RequestDrainTracker):
        raise RuntimeError("FastAPI request drain state has an invalid owner")
    return existing


def require_request_drain_tracker(request: Request) -> RequestDrainTracker:
    tracker = getattr(request.app.state, _APP_STATE_ATTRIBUTE, None)
    if not isinstance(tracker, RequestDrainTracker):
        raise RuntimeError("FastAPI request drain tracker is not installed")
    return tracker


def _draining_http_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "service_stopping",
            "message": "backend host is stopping; state-changing requests are unavailable",
        },
    )


@contextmanager
def admitted_state_change(request: Request) -> Iterator[None]:
    """Count one actual state-changing execution or reject it fail-closed."""
    tracker = require_request_drain_tracker(request)
    try:
        tracker.enter()
    except RequestDrainRejected as exc:
        raise _draining_http_error() from exc
    try:
        yield
    finally:
        tracker.leave()


def _request_argument(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Request:
    candidate = kwargs.get("request")
    if candidate is None:
        candidate = signature.bind_partial(*args, **kwargs).arguments.get("request")
    if not isinstance(candidate, Request):
        raise RuntimeError("state-changing endpoint did not receive its Request argument")
    return candidate


def _wrap_state_changing_endpoint(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(endpoint, _WRAPPED_ATTRIBUTE, False):
        return endpoint
    if inspect.isgeneratorfunction(endpoint) or inspect.isasyncgenfunction(endpoint):
        raise RuntimeError("state-changing streaming endpoints are not supported")

    signature = inspect.signature(endpoint)
    if "request" not in signature.parameters:
        raise RuntimeError(
            f"state-changing endpoint {endpoint.__module__}.{endpoint.__name__} "
            "must declare request: Request"
        )

    if inspect.iscoroutinefunction(endpoint):

        @wraps(endpoint)
        async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
            request = _request_argument(signature, args, kwargs)
            with admitted_state_change(request):
                return await endpoint(*args, **kwargs)

        wrapped: Callable[..., Any] = _async_wrapped
    else:

        @wraps(endpoint)
        def _sync_wrapped(*args: Any, **kwargs: Any) -> Any:
            request = _request_argument(signature, args, kwargs)
            with admitted_state_change(request):
                return endpoint(*args, **kwargs)

        wrapped = _sync_wrapped

    setattr(wrapped, _WRAPPED_ATTRIBUTE, True)
    return wrapped


class StateChangingAPIRoute(APIRoute):
    """APIRoute that counts the real sync or async mutation execution."""

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        methods: set[str] | list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        normalized_methods = {method.upper() for method in (methods or {"GET"})}
        if normalized_methods & STATE_CHANGING_METHODS:
            endpoint = _wrap_state_changing_endpoint(endpoint)
        super().__init__(path, endpoint, methods=methods, **kwargs)

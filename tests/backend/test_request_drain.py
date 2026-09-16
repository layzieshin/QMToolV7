"""Request-drain owner: atomic admission and endpoint-level tracking."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.backend import auth_dependencies
from src.backend.request_drain import (
    RequestDrainPhase,
    RequestDrainRejected,
    RequestDrainTracker,
    StateChangingAPIRoute,
    ensure_request_drain_tracker,
)


def _tracked_app() -> tuple[FastAPI, RequestDrainTracker, APIRouter]:
    app = FastAPI()
    tracker = ensure_request_drain_tracker(app)
    router = APIRouter(route_class=StateChangingAPIRoute)
    return app, tracker, router


def test_tracker_admission_drain_wait_timeout_and_idempotence() -> None:
    tracker = RequestDrainTracker()
    tracker.enter()
    assert tracker.active_count == 1
    tracker.begin_drain()
    tracker.begin_drain()
    assert tracker.phase is RequestDrainPhase.DRAINING
    with pytest.raises(RequestDrainRejected, match="stopping"):
        tracker.enter()
    assert tracker.wait_until_idle(timeout=0.01) is False
    tracker.leave()
    assert tracker.wait_until_idle(timeout=0.01) is True
    assert tracker.active_count == 0
    with pytest.raises(RuntimeError, match="underflow"):
        tracker.leave()


def test_sync_endpoint_is_counted_inside_worker_and_rejects_after_drain() -> None:
    app, tracker, router = _tracked_app()
    entered = threading.Event()
    release = threading.Event()
    endpoint_thread: list[int] = []
    result: dict[str, object] = {}

    @router.post("/mutate")
    def mutate(request: Request) -> dict[str, str]:
        endpoint_thread.append(threading.get_ident())
        entered.set()
        assert release.wait(timeout=5.0)
        return {"status": "written"}

    @router.get("/public")
    def public_read() -> dict[str, str]:
        return {"status": "readable"}

    app.include_router(router)

    def _request() -> None:
        with TestClient(app) as client:
            response = client.post("/mutate")
            result["status"] = response.status_code
            result["body"] = response.json()

    request_thread = threading.Thread(target=_request, name="request-drain-sync-client")
    request_thread.start()
    assert entered.wait(timeout=3.0)
    assert tracker.active_count == 1

    tracker.begin_drain()
    with TestClient(app) as client:
        rejected = client.post("/mutate")
        assert rejected.status_code == 503
        assert rejected.json()["detail"]["error"] == "service_stopping"
        assert client.get("/public").status_code == 200
    assert len(endpoint_thread) == 1
    assert tracker.wait_until_idle(timeout=0.01) is False

    release.set()
    request_thread.join(timeout=5.0)
    assert not request_thread.is_alive()
    assert result == {"status": 200, "body": {"status": "written"}}
    assert tracker.wait_until_idle(timeout=0.5) is True


def test_async_endpoint_remains_counted_until_coroutine_finishes() -> None:
    app, tracker, router = _tracked_app()
    entered = threading.Event()
    release = threading.Event()
    result: dict[str, object] = {}

    @router.post("/mutate")
    async def mutate(request: Request) -> dict[str, str]:
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {"status": "written"}

    app.include_router(router)

    def _request() -> None:
        with TestClient(app) as client:
            response = client.post("/mutate")
            result["status"] = response.status_code

    request_thread = threading.Thread(target=_request, name="request-drain-async-client")
    request_thread.start()
    assert entered.wait(timeout=3.0)
    tracker.begin_drain()
    assert tracker.active_count == 1
    assert tracker.wait_until_idle(timeout=0.01) is False
    release.set()
    request_thread.join(timeout=5.0)
    assert not request_thread.is_alive()
    assert result == {"status": 200}
    assert tracker.active_count == 0


def test_unsafe_endpoint_without_request_fails_at_route_build() -> None:
    router = APIRouter(route_class=StateChangingAPIRoute)
    with pytest.raises(RuntimeError, match="must declare request"):

        @router.post("/invalid")
        def invalid() -> dict[str, bool]:
            return {"invalid": True}


def test_authenticated_safe_read_session_touch_is_blocked_after_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    tracker = ensure_request_drain_tracker(app)
    app.state.container = object()
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/me",
            "headers": [],
            "app": app,
        }
    )
    calls: list[str] = []
    context = object()

    def _resolve_session(container, token, *, request_id, password_change_allowed):
        calls.append(token)
        assert tracker.active_count == 1
        return context

    monkeypatch.setattr(auth_dependencies.um_api, "resolve_session", _resolve_session)
    assert (
        auth_dependencies.require_user_context(
            request,
            "session-a",
            "request-a",
            password_change_allowed=False,
        )
        is context
    )
    assert calls == ["session-a"]
    assert tracker.active_count == 0

    tracker.begin_drain()
    with pytest.raises(HTTPException) as exc_info:
        auth_dependencies.require_user_context(
            request,
            "session-b",
            "request-b",
            password_change_allowed=False,
        )
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "service_stopping"
    assert calls == ["session-a"]


def test_wait_until_idle_unblocks_only_after_last_execution_leaves() -> None:
    tracker = RequestDrainTracker()
    tracker.enter()
    tracker.enter()
    tracker.begin_drain()
    result: list[bool] = []

    def _waiter() -> None:
        result.append(tracker.wait_until_idle(timeout=1.0))

    waiter = threading.Thread(target=_waiter, name="request-drain-waiter")
    waiter.start()
    time.sleep(0.02)
    tracker.leave()
    time.sleep(0.02)
    assert waiter.is_alive()
    tracker.leave()
    waiter.join(timeout=1.0)
    assert result == [True]

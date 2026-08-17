"""Standalone client worker subprocess for J04-M0 real-process acceptance (test-only).

Holds an in-memory backend session in this process only. Never prints raw tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any

from interfaces.clients.backend_session import BackendSessionApi
from interfaces.clients.http_transport import BackendTransportError


def _token_fingerprint(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return digest[:16]


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.flush()


def _parse_json_object(raw: str, *, field_name: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J04-M0 acceptance client worker (test-only)")
    parser.add_argument(
        "--action",
        choices=("login", "me", "ping", "http"),
        required=True,
        help="Worker action",
    )
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="")
    parser.add_argument("--headers-json", default="{}")
    parser.add_argument("--body-json", default="")
    ns = parser.parse_args(argv)

    if ns.action == "ping":
        _emit({"ok": True, "action": "ping", "home": os.environ.get("QMTOOL_HOME", "")})
        return 0

    session = BackendSessionApi()
    if ns.action == "login":
        user = session.login(ns.username, ns.password)
        token = session.bearer_token() or ""
        _emit(
            {
                "ok": True,
                "action": "login",
                "username": user.username,
                "token_fingerprint": _token_fingerprint(token) if token else "",
                "home": os.environ.get("QMTOOL_HOME", ""),
            }
        )
        return 0

    if ns.action == "me":
        if not ns.username or not ns.password:
            _emit({"ok": False, "action": "me", "error": "username/password required"})
            return 2
        session.login(ns.username, ns.password)
        user = session.refresh_me()
        _emit(
            {
                "ok": True,
                "action": "me",
                "username": user.username,
                "user_id": user.user_id,
                "home": os.environ.get("QMTOOL_HOME", ""),
            }
        )
        return 0

    if ns.action == "http":
        if not ns.path.startswith("/"):
            _emit({"ok": False, "action": "http", "error": "path must start with /"})
            return 2
        if ns.username:
            session.login(ns.username, ns.password)
        try:
            headers = _parse_json_object(ns.headers_json, field_name="headers-json")
            body = _parse_json_object(ns.body_json, field_name="body-json")
            payload = session._transport.request(  # noqa: SLF001 test-only worker
                ns.method.upper(),
                ns.path,
                body=body or None,
                headers=headers or None,
            )
            status = 200
            etag = ""
            if isinstance(payload, dict):
                etag = str(payload.get("etag", "")).strip()
            _emit(
                {
                    "ok": True,
                    "action": "http",
                    "status": status,
                    "etag": etag,
                    "body": payload,
                    "home": os.environ.get("QMTOOL_HOME", ""),
                }
            )
            return 0
        except BackendTransportError as exc:
            parsed: Any = exc.body
            if isinstance(exc.body, str):
                try:
                    parsed = json.loads(exc.body)
                except json.JSONDecodeError:
                    parsed = exc.body
            _emit(
                {
                    "ok": True,
                    "action": "http",
                    "status": exc.status_code or 0,
                    "body": parsed,
                    "home": os.environ.get("QMTOOL_HOME", ""),
                }
            )
            return 0

    _emit({"ok": False, "error": "unsupported action"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

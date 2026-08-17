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


def _token_fingerprint(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return digest[:16]


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J04-M0 acceptance client worker (test-only)")
    parser.add_argument(
        "--action",
        choices=("login", "me", "ping"),
        required=True,
        help="Worker action",
    )
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
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

    _emit({"ok": False, "error": "unsupported action"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

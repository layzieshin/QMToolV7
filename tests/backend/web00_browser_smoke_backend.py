"""Ephemeral FastAPI backend for WEB00 real-browser HTTPS smoke (test container only)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import uvicorn

from src.backend.api import create_app
from tests.backend.test_auth_api import _build_test_container


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="web00-browser-smoke-"))
    container, _repo, _service = _build_test_container(tmp)
    host = os.environ.get("WEB00_SMOKE_BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB00_SMOKE_BACKEND_PORT", "18765"))
    uvicorn.run(
        create_app(container),
        host=host,
        port=port,
        log_level=os.environ.get("WEB00_SMOKE_BACKEND_LOG", "warning"),
    )


if __name__ == "__main__":
    main()

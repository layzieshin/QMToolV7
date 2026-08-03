"""Shared pytest bootstrap for local environment files."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = _ROOT / ".env"
_PYTEST_BUILD_DIR = _ROOT / "build"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _ensure_pg_dsn() -> None:
    if os.environ.get("QMTOOL_PG_DSN", "").strip():
        return
    host = os.environ.get("QMTOOL_PG_HOST", "").strip()
    database = os.environ.get("QMTOOL_PG_DATABASE", "").strip()
    user = os.environ.get("QMTOOL_PG_USER", "").strip()
    password = os.environ.get("QMTOOL_PG_PASSWORD", "")
    if not (host and database and user and password):
        return
    port = os.environ.get("QMTOOL_PG_PORT", "5432").strip() or "5432"
    os.environ["QMTOOL_PG_DSN"] = (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


_PYTEST_BUILD_DIR.mkdir(parents=True, exist_ok=True)
_load_dotenv(_ENV_PATH)
_ensure_pg_dsn()

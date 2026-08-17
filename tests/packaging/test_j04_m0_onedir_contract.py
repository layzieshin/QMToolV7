"""Static J04-M0 onedir packaging contract (no real PyInstaller build)."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

from interfaces.clients.http_transport import resolve_backend_base_url_from_env

_REPO = Path(__file__).resolve().parents[2]
_BUILD_ONEDIR = _REPO / "packaging" / "build_onedir.py"


def _load_build_onedir():
    spec = importlib.util.spec_from_file_location("build_onedir", _BUILD_ONEDIR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_onedir")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hidden_imports_from_build_script() -> set[str]:
    tree = ast.parse(_BUILD_ONEDIR.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_HIDDEN_IMPORTS" and node.value is not None:
                value = ast.literal_eval(node.value)
                return set(value)
    raise AssertionError("_HIDDEN_IMPORTS not found in build_onedir.py")


def test_build_onedir_uses_pyqt_entrypoint() -> None:
    build = _load_build_onedir()
    entry = str(build.ENTRY).replace("\\", "/")
    assert entry.endswith("interfaces/pyqt/main.py")


def test_build_onedir_does_not_bake_backend_url() -> None:
    text = _BUILD_ONEDIR.read_text(encoding="utf-8")
    assert "QMTOOL_BACKEND_URL" not in text


def test_build_onedir_includes_j04_client_runtime_hidden_imports() -> None:
    hidden = _hidden_imports_from_build_script()
    required = {
        "fitz",
        "pypdf",
        "pythoncom",
        "win32com.client",
        "interfaces.clients.backend_session",
        "interfaces.clients.documents_http_ports",
        "interfaces.clients.signature_http_ports",
        "interfaces.clients.http_transport",
        "qm_platform.runtime.client_runtime_profile",
    }
    missing = required - hidden
    assert not missing, f"missing hidden imports: {sorted(missing)}"


def test_build_onedir_bundles_prod_public_key_only() -> None:
    text = _BUILD_ONEDIR.read_text(encoding="utf-8")
    assert "prod_ed25519_public.pem" in text
    assert "prod_ed25519_private.pem" not in text


def test_backend_url_is_resolved_at_runtime_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMTOOL_BACKEND_URL", "http://127.0.0.1:9001")
    assert resolve_backend_base_url_from_env() == "http://127.0.0.1:9001"
    monkeypatch.delenv("QMTOOL_BACKEND_URL", raising=False)
    assert resolve_backend_base_url_from_env() == "http://127.0.0.1:8000"

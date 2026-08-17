from __future__ import annotations

import pytest

from interfaces.gui import main as gui_main
from modules.documents.errors import DocumentWorkflowError


class _NoopLifecycle:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class _FakeContainer:
    def __init__(self) -> None:
        self._ports = {
            "usermanagement_service": object(),
            "documents_pool_api": object(),
            "documents_workflow_api": object(),
            "settings_service": object(),
        }

    def get_port(self, name: str):
        return self._ports[name]


def test_legacy_tk_initializes_without_documents_service(monkeypatch) -> None:
    monkeypatch.setattr(gui_main, "build_container", lambda: _FakeContainer())
    monkeypatch.setattr(gui_main, "register_core_modules", lambda _container: _NoopLifecycle())
    controller = gui_main.UiController()
    assert controller.documents_pool_api is not None


def test_legacy_tk_documents_actions_fail_closed_before_port_use(monkeypatch) -> None:
    monkeypatch.setattr(gui_main, "build_container", lambda: _FakeContainer())
    monkeypatch.setattr(gui_main, "register_core_modules", lambda _container: _NoopLifecycle())
    controller = gui_main.UiController()
    with pytest.raises(DocumentWorkflowError, match="fail-closed"):
        controller.assign_roles("DOC-1", 1, {"u1"}, {"u2"}, {"u3"})

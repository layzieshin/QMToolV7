from __future__ import annotations

from pathlib import Path

from interfaces.pyqt.runtime.host import RuntimeHost


def test_pyqt_backend_profile_wires_only_transition_modules(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.setenv("QMTOOL_LICENSE_MODE", "dev")
    host = RuntimeHost()
    try:
        host.start()
        assert host.lifecycle is not None
        assert host.lifecycle.registered_module_ids() == ["documents", "signature"]
        assert host.require_container().get_port("client_runtime_profile") == "backend"
        assert host.require_container().get_port("enabled_pyqt_contribution_ids") == frozenset(
            {"documents.pool", "documents.workflow"}
        )
        database_names = {path.name for path in Path(tmp_path).rglob("*.db")}
        assert "users.db" not in database_names
        assert "documents.db" not in database_names
        assert "templates.db" not in database_names
    finally:
        host.stop()

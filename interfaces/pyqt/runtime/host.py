from __future__ import annotations

from dataclasses import dataclass

from interfaces.cli.bootstrap import build_container
from qm_platform.runtime.bootstrap import register_core_modules
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager


@dataclass
class RuntimeHost:
    """
    Owns the modular runtime for the Qt shell.

    Uses the same container wiring as CLI/Tk without modifying those modules.
    """

    container: RuntimeContainer | None = None
    lifecycle: LifecycleManager | None = None

    def start(self) -> None:
        if self.container is not None:
            return
        from qm_platform.runtime.client_runtime_profile import PROFILE_BACKEND

        self.container = build_container(client_runtime_profile=PROFILE_BACKEND)
        # Compose the identity/session ports before any consumer is wired. The
        # backend transition client does not prepare local usermanagement,
        # incident, training-admin or registry contracts.
        from interfaces.clients.backend_identity import BackendIdentityAdapter
        from interfaces.clients.backend_session import create_backend_session_api
        from interfaces.clients.documents_http import bind_pyqt_session_token_provider
        from interfaces.clients.signature_http import bind_pyqt_session_token_provider as bind_signature_session_token_provider

        session = create_backend_session_api()
        self.container.register_port("backend_session_api", session)
        bind_pyqt_session_token_provider(session.bearer_token)
        bind_signature_session_token_provider(session.bearer_token)
        # Identity for PyQt consumers: session + HTTP directory, no local
        # shadow login. This reference is registered before module wiring.
        identity = BackendIdentityAdapter(session)
        self.container.register_port("usermanagement_service", identity)
        self.container.register_port("backend_identity", self.container.get_port("usermanagement_service"))
        self.container.register_port(
            "enabled_pyqt_contribution_ids",
            frozenset({"documents.pool", "documents.workflow"}),
        )
        self.lifecycle = register_core_modules(
            self.container,
            module_ids={"documents", "signature"},
        )
        self.lifecycle.start(strict=True)

    def stop(self) -> None:
        from interfaces.clients.documents_http import clear_pyqt_session_token_provider
        from interfaces.clients.documents_http import clear_artifact_temp_files
        from interfaces.clients.signature_http import clear_pyqt_session_token_provider as clear_signature_session_token_provider

        clear_artifact_temp_files()
        clear_pyqt_session_token_provider()
        clear_signature_session_token_provider()
        if self.lifecycle is not None:
            self.lifecycle.stop()
            self.lifecycle = None
        self.container = None

    def require_container(self) -> RuntimeContainer:
        if self.container is None:
            raise RuntimeError("runtime not started")
        return self.container

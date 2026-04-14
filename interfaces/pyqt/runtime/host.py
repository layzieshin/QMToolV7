from __future__ import annotations

from dataclasses import dataclass

from interfaces.cli.main import build_container
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
        self.container = build_container()
        self.lifecycle = register_core_modules(self.container)
        self.lifecycle.start(strict=False)

    def stop(self) -> None:
        if self.lifecycle is not None:
            self.lifecycle.stop()
            self.lifecycle = None
        self.container = None

    def require_container(self) -> RuntimeContainer:
        if self.container is None:
            raise RuntimeError("runtime not started")
        return self.container

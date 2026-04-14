from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget

from qm_platform.runtime.container import RuntimeContainer


@dataclass(frozen=True)
class QtModuleContribution:
    """
    Fixed contract for registering a module area in the PyQt shell.

    - contribution_id: unique key for navigation and lazy widget cache
    - module_id: logical owner (matches platform module_id where applicable)
    - factory(container): must return a QWidget; runs on the GUI thread after first nav selection
    """

    contribution_id: str
    module_id: str
    title: str
    sort_order: int
    factory: Callable[[RuntimeContainer], QWidget]
    requires_login: bool = True
    allowed_roles: tuple[str, ...] | None = None

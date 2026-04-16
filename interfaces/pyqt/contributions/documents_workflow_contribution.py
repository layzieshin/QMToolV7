"""
Contribution registration for the Documents Workflow area.

This module is the sole entry point for the registry catalog.
All UI composition lives in ``documents_workflow_view.py``.
"""
from __future__ import annotations

from interfaces.pyqt.contributions.documents_workflow_view import DocumentsWorkflowWidget
from interfaces.pyqt.registry.contribution import QtModuleContribution
from qm_platform.runtime.container import RuntimeContainer
from PyQt6.QtWidgets import QWidget


def _build(container: RuntimeContainer) -> QWidget:
    return DocumentsWorkflowWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="documents.workflow",
            module_id="documents",
            title="Dokumentenlenkung",
            sort_order=10,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]


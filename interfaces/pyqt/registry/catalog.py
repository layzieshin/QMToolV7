from __future__ import annotations

"""
Aggregate UI contributions for the PyQt shell.

To add a module screen: (1) add ``interfaces/pyqt/contributions/<name>.py`` exposing
``contributions() -> list[QtModuleContribution]`` with a ``factory(container) -> QWidget``;
(2) import it here and extend ``items`` in ``all_contributions``. No changes to
``modules/*`` or ``platform/*`` are required.
"""

from interfaces.pyqt.contributions import (
    admin_debug_view,
    audit_logs_view,
    documents_pool_view,
    documents_workflow_contribution,
    home_view,
    settings_view,
    signature_view,
    training_placeholder,
)
from interfaces.pyqt.registry.contribution import QtModuleContribution


def all_contributions() -> list[QtModuleContribution]:
    items: list[QtModuleContribution] = []
    items.extend(home_view.contributions())
    items.extend(documents_workflow_contribution.contributions())
    items.extend(documents_pool_view.contributions())
    items.extend(signature_view.contributions())
    items.extend(training_placeholder.contributions())
    items.extend(settings_view.contributions())
    items.extend(audit_logs_view.contributions())
    items.extend(admin_debug_view.contributions())
    return sorted(items, key=lambda c: (c.sort_order, c.title))

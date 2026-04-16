"""Scope-based assignment resolution (§3.2)."""
from __future__ import annotations

from .contracts import TrainingDocumentRef


class ScopeResolver:
    """Pure logic: checks whether a user's scope matches a document's scope."""

    @staticmethod
    def matches(
        doc: TrainingDocumentRef,
        *,
        user_department: str | None,
        user_scope: str | None,
        user_organization_unit: str | None,
    ) -> bool:
        # A document is scope-relevant if any of department/site/regulatory_scope
        # overlaps with the user's attributes.  Empty doc scope = relevant to all.
        if not doc.department and not doc.site and not doc.regulatory_scope:
            return True
        if doc.department and user_department:
            if doc.department.strip().upper() == user_department.strip().upper():
                return True
        if doc.site and user_scope:
            if doc.site.strip().upper() == user_scope.strip().upper():
                return True
        if doc.regulatory_scope and user_organization_unit:
            if doc.regulatory_scope.strip().upper() == user_organization_unit.strip().upper():
                return True
        return False


"""Training assignment resolver – merges scope, tags, manual, exemption (§3.9).

Priority order (§1.4):
  1. Exemption (overrides all)
  2. Manual assignment
  3. Tag match
  4. Scope match
"""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import AssignmentSource, TrainingDocumentRef


class TrainingAssignmentResolver:
    @staticmethod
    def resolve(
        doc: TrainingDocumentRef,
        *,
        scope_match: bool,
        tag_match: bool,
        manual_match: bool,
        exempted: bool,
        exemption_expired: bool = False,
    ) -> AssignmentSource:
        """Return the effective assignment source for a user+document pair."""
        # If actively exempted and not expired => EXEMPTED
        if exempted and not exemption_expired:
            return AssignmentSource.EXEMPTED
        # Positive assignment sources in priority order
        if manual_match:
            return AssignmentSource.MANUAL
        if tag_match:
            return AssignmentSource.TAG
        if scope_match:
            return AssignmentSource.SCOPE
        return AssignmentSource.NOT_RELEVANT


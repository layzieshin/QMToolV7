from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import ActionType, IncidentAssessmentInput, IncidentClassification
from tests.modules.test_incident_management_capa_rules import IncidentManagementActionsTest  # noqa: F401
from tests.modules.test_incident_management_effectiveness import IncidentManagementClosureRulesTest  # noqa: F401

if __name__ == "__main__":
    unittest.main()

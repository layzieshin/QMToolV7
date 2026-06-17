"""Incident management workspace sections."""
from __future__ import annotations

from interfaces.pyqt.contributions.incident_management_sections.actions_section import ActionsSection
from interfaces.pyqt.contributions.incident_management_sections.capa_section import CapaSection
from interfaces.pyqt.contributions.incident_management_sections.effectiveness_section import EffectivenessSection
from interfaces.pyqt.contributions.incident_management_sections.inquiries_section import InquiriesSection
from interfaces.pyqt.contributions.incident_management_sections.leadership_section import LeadershipSection
from interfaces.pyqt.contributions.incident_management_sections.management_review_section import (
    ManagementReviewSection,
)
from interfaces.pyqt.contributions.incident_management_sections.my_incidents_section import MyIncidentsSection
from interfaces.pyqt.contributions.incident_management_sections.qmb_review_section import QmbReviewSection
from interfaces.pyqt.contributions.incident_management_sections.register_section import RegisterSection
from interfaces.pyqt.contributions.incident_management_sections.reports_section import ReportsSection
from interfaces.pyqt.contributions.incident_management_sections.settings_section import SettingsSection
from interfaces.pyqt.contributions.incident_management_sections.submit_section import ReportEventSection

__all__ = [
    "ActionsSection",
    "CapaSection",
    "EffectivenessSection",
    "InquiriesSection",
    "LeadershipSection",
    "ManagementReviewSection",
    "MyIncidentsSection",
    "QmbReviewSection",
    "RegisterSection",
    "ReportEventSection",
    "ReportsSection",
    "SettingsSection",
]

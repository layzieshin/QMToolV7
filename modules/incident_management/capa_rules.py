"""CAPA requirement derivation from assessment and settings."""
from __future__ import annotations

from .contracts import IncidentAssessmentInput


def derive_capa_required(assessment: IncidentAssessmentInput, settings: dict) -> bool:
    rules = settings.get("capa_required_rules") or {}
    if assessment.is_critical and bool(rules.get("critical", True)):
        return True
    if assessment.is_repeated and bool(rules.get("repeated", True)):
        return True
    if assessment.patient_safety_relevant and bool(rules.get("patient_safety", True)):
        return True
    if assessment.system_risk_relevant and bool(rules.get("system_risk", True)):
        return True
    if assessment.formal_deviation and bool(rules.get("formal_deviation", True)):
        return True
    if assessment.result_correctness_issue and bool(rules.get("result_correctness", True)):
        return True
    if assessment.escalation_required and bool(rules.get("escalation", True)):
        return True
    return bool(assessment.capa_required)

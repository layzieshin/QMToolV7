from __future__ import annotations

from modules.incident_management.contracts import IncidentClassification
from interfaces.pyqt.presenters.incident_management_presenter import IncidentManagementPresenter


def test_presenter_classification_labels_include_near_miss_and_risk() -> None:
    labels = IncidentManagementPresenter.CLASSIFICATION_LABELS
    assert labels[IncidentClassification.NEAR_MISS] == "Beinahe-Ereignis"
    assert labels[IncidentClassification.RISK] == "Risiko"


def test_presenter_formats_optional_bool() -> None:
    assert IncidentManagementPresenter.format_optional_bool(True) == "Ja"
    assert IncidentManagementPresenter.format_optional_bool(False) == "Nein"
    assert IncidentManagementPresenter.format_optional_bool(None) == "-"

from __future__ import annotations

from pathlib import Path


def _source() -> str:
    return Path("interfaces/pyqt/contributions/signature_view.py").read_text(encoding="utf-8")


def _wizard_source() -> str:
    return Path("interfaces/pyqt/widgets/signature_sign_wizard.py").read_text(encoding="utf-8")


def test_signature_view_exposes_single_sign_button_label() -> None:
    src = _source()
    assert 'QPushButton("Dokument signieren")' in src


def test_signature_view_no_longer_contains_legacy_toolbar_buttons() -> None:
    src = _source()
    assert 'QPushButton("Eingabe-PDF waehlen")' not in src
    assert 'QPushButton("Signatur verwalten")' not in src
    assert 'QPushButton("Dokument ad-hoc signieren")' not in src


def test_sign_wizard_uses_separate_password_step_without_canvas_button() -> None:
    src = _wizard_source()
    assert 'QPushButton("Signatur zeichnen")' not in src
    assert 'Schritt 4 / 4' in src
    assert 'showFullScreen()' in src

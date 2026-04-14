from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QToolButton, QVBoxLayout, QWidget

from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput


class SignatureRequestForm(QWidget):
    """Reusable GUI form that only collects sign request input."""

    def __init__(self) -> None:
        super().__init__()
        self.profile = QComboBox()
        self.profile.addItem("Eigene Parameter", "")

        self.input_pdf = QLineEdit()
        self.output_pdf = QLineEdit()
        self.signature_png = QLineEdit()
        self.page_index = QLineEdit("0")
        self.x = QLineEdit("100")
        self.y = QLineEdit("100")
        self.width = QLineEdit("120")
        self.size_preset = QComboBox()
        self.size_preset.addItems(["Klein (90)", "Mittel (120)", "Groß (160)", "Sehr groß (220)"])
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.dry_run = QCheckBox("Trockenlauf")
        self.dry_run.setChecked(True)
        self.show_name = QCheckBox("Name anzeigen")
        self.show_name.setChecked(True)
        self.show_date = QCheckBox("Datum anzeigen")
        self.show_date.setChecked(True)
        self.name_position = QComboBox()
        self.name_position.addItems(["above", "below", "off"])
        self.date_position = QComboBox()
        self.date_position.addItems(["above", "below", "off"])
        self.name_font_size = QLineEdit("12")
        self.date_font_size = QLineEdit("12")
        self.name_rel_x = QLineEdit("")
        self.name_rel_y = QLineEdit("")
        self.date_rel_x = QLineEdit("")
        self.date_rel_y = QLineEdit("")
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self._advanced_toggle = QToolButton()
        self._advanced_toggle.setText("Erweiterte Layout-Optionen anzeigen")
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setChecked(False)
        self._advanced_toggle.toggled.connect(self._toggle_advanced_fields)

        base_form = QFormLayout()
        base_form.addRow("Signaturprofil", self.profile)
        base_form.addRow("Eingabe-PDF", self.input_pdf)
        base_form.addRow("Ausgabe-PDF", self.output_pdf)
        base_form.addRow("Signaturbild PNG/GIF", self.signature_png)
        base_form.addRow("Seitenindex", self.page_index)
        base_form.addRow("X", self.x)
        base_form.addRow("Y", self.y)
        base_form.addRow("Zielbreite", self.width)
        base_form.addRow("Groessen-Preset", self.size_preset)
        base_form.addRow("Signier-Passwort", self.password)
        base_form.addRow("", self.dry_run)
        base_form.addRow("Preview", self.preview)

        self._advanced_widget = QWidget()
        advanced_form = QFormLayout(self._advanced_widget)
        advanced_form.addRow("", self.show_name)
        advanced_form.addRow("Name-Position", self.name_position)
        advanced_form.addRow("Name Font", self.name_font_size)
        advanced_form.addRow("Name rel X", self.name_rel_x)
        advanced_form.addRow("Name rel Y", self.name_rel_y)
        advanced_form.addRow("", self.show_date)
        advanced_form.addRow("Datum-Position", self.date_position)
        advanced_form.addRow("Datum Font", self.date_font_size)
        advanced_form.addRow("Datum rel X", self.date_rel_x)
        advanced_form.addRow("Datum rel Y", self.date_rel_y)
        self._advanced_widget.setVisible(False)

        root = QVBoxLayout(self)
        root.addLayout(base_form)
        root.addWidget(self._advanced_toggle)
        root.addWidget(self._advanced_widget)

        self.width.textChanged.connect(lambda _text: self._update_preview())
        self.x.textChanged.connect(lambda _text: self._update_preview())
        self.y.textChanged.connect(lambda _text: self._update_preview())
        self.show_name.toggled.connect(lambda _checked: self._update_preview())
        self.show_date.toggled.connect(lambda _checked: self._update_preview())
        self.name_position.currentTextChanged.connect(lambda _text: self._update_preview())
        self.date_position.currentTextChanged.connect(lambda _text: self._update_preview())
        self.size_preset.currentTextChanged.connect(self._apply_preset)
        self._apply_preset(self.size_preset.currentText())
        self._update_preview()

    def has_input(self) -> bool:
        return bool(self.input_pdf.text().strip())

    def set_profiles(self, names: list[str] | list[tuple[str, str]]) -> None:
        current = self.profile.currentText()
        self.profile.clear()
        self.profile.addItem("Eigene Parameter", "")
        for item in names:
            if isinstance(item, tuple):
                template_id, name = item
                self.profile.addItem(name, template_id)
            else:
                self.profile.addItem(item, item)
        idx = self.profile.findText(current)
        if idx >= 0:
            self.profile.setCurrentIndex(idx)

    def selected_profile(self) -> str | None:
        text = self.profile.currentText().strip()
        if not text or text == "Eigene Parameter":
            return None
        data = self.profile.currentData()
        if isinstance(data, str) and data.strip():
            return data.strip()
        return text

    def _apply_preset(self, preset: str) -> None:
        if "Klein" in preset:
            self.width.setText("90")
        elif "Mittel" in preset:
            self.width.setText("120")
        elif "Sehr groß" in preset:
            self.width.setText("220")
        elif "Groß" in preset:
            self.width.setText("160")
        self._update_preview()

    def _toggle_advanced_fields(self, visible: bool) -> None:
        self._advanced_widget.setVisible(visible)
        self._advanced_toggle.setText(
            "Erweiterte Layout-Optionen ausblenden" if visible else "Erweiterte Layout-Optionen anzeigen"
        )

    def _update_preview(self) -> None:
        self.preview.setText(
            f"Signaturgröße: {self.width.text().strip()}px | Position: x={self.x.text().strip()}, y={self.y.text().strip()} | "
            f"Name: {'an' if self.show_name.isChecked() else 'aus'} ({self.name_position.currentText()}) | "
            f"Datum: {'an' if self.show_date.isChecked() else 'aus'} ({self.date_position.currentText()})"
        )

    def build_request(self, *, signer_user: str, reason: str) -> SignRequest:
        return SignRequest(
            input_pdf=Path(self.input_pdf.text().strip()),
            output_pdf=Path(self.output_pdf.text().strip()) if self.output_pdf.text().strip() else None,
            signature_png=Path(self.signature_png.text().strip()) if self.signature_png.text().strip() else None,
            placement=SignaturePlacementInput(
                page_index=int(self.page_index.text().strip()),
                x=float(self.x.text().strip()),
                y=float(self.y.text().strip()),
                target_width=float(self.width.text().strip()),
            ),
            layout=LabelLayoutInput(
                show_signature=True,
                show_name=self.show_name.isChecked(),
                show_date=self.show_date.isChecked(),
                name_position=self.name_position.currentText(),  # type: ignore[arg-type]
                date_position=self.date_position.currentText(),  # type: ignore[arg-type]
                name_font_size=int(self.name_font_size.text().strip() or "12"),
                date_font_size=int(self.date_font_size.text().strip() or "12"),
                name_rel_x=float(self.name_rel_x.text().strip()) if self.name_rel_x.text().strip() else None,
                name_rel_y=float(self.name_rel_y.text().strip()) if self.name_rel_y.text().strip() else None,
                date_rel_x=float(self.date_rel_x.text().strip()) if self.date_rel_x.text().strip() else None,
                date_rel_y=float(self.date_rel_y.text().strip()) if self.date_rel_y.text().strip() else None,
            ),
            overwrite_output=False,
            dry_run=self.dry_run.isChecked(),
            sign_mode="visual",
            signer_user=signer_user,
            password=self.password.text().strip() or None,
            reason=reason,
        )

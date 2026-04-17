from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class QuizDialog(QDialog):
    def __init__(self, session, questions, api, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Quiz – {session.document_id} v{session.version}")
        self.setMinimumSize(700, 520)
        self._session = session
        self._questions = questions
        self._api = api
        self._index = 0
        self._selected_answers: list[str | None] = [None] * len(questions)

        layout = QVBoxLayout(self)
        self._progress_label = QLabel("")
        self._progress = QProgressBar()
        self._progress.setRange(0, max(1, len(questions)))
        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        self._answers_box = QGroupBox("Antworten")
        self._answers_layout = QVBoxLayout(self._answers_box)
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._answer_buttons: list[QRadioButton] = []

        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress)
        layout.addWidget(self._question_label)
        layout.addWidget(self._answers_box, stretch=1)

        nav = QHBoxLayout()
        self._btn_prev = QPushButton("Zurueck")
        self._btn_prev.clicked.connect(self._prev)
        self._btn_next = QPushButton("Weiter")
        self._btn_next.clicked.connect(self._next)
        self._btn_submit = QPushButton("Quiz abgeben")
        self._btn_submit.clicked.connect(self._submit)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._btn_next)
        nav.addStretch(1)
        nav.addWidget(self._btn_submit)
        layout.addLayout(nav)

        self.setStyleSheet(
            "QRadioButton { padding: 6px; border-radius: 4px; }"
            "QRadioButton:checked { background-color: #c8c8c8; }"
        )
        self._render_current()

    def _clear_answer_controls(self) -> None:
        while self._answers_layout.count():
            item = self._answers_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._answer_buttons = []

    def _render_current(self) -> None:
        total = len(self._questions)
        question = self._questions[self._index]
        self._progress_label.setText(f"Frage {self._index + 1} von {total}")
        self._progress.setValue(self._index + 1)
        self._question_label.setText(question.text)
        self._clear_answer_controls()
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        for answer in question.answers:
            btn = QRadioButton(answer.text)
            btn.setProperty("answer_id", answer.answer_id)
            btn.toggled.connect(self._on_answer_toggled)
            self._answers_layout.addWidget(btn)
            self._button_group.addButton(btn)
            self._answer_buttons.append(btn)
        selected_answer = self._selected_answers[self._index]
        if selected_answer is not None:
            for btn in self._answer_buttons:
                if str(btn.property("answer_id")) == selected_answer:
                    btn.setChecked(True)
                    break
        self._btn_prev.setEnabled(self._index > 0)
        self._btn_next.setEnabled(self._index < total - 1)

    def _on_answer_toggled(self, checked: bool) -> None:
        if not checked:
            return
        btn = self.sender()
        if btn is None:
            return
        self._selected_answers[self._index] = str(btn.property("answer_id"))

    def _prev(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._render_current()

    def _next(self) -> None:
        if self._index >= len(self._questions) - 1:
            return
        self._index += 1
        self._render_current()

    def _submit(self) -> None:
        if any(a is None for a in self._selected_answers):
            reply = QMessageBox.question(
                self,
                "Quiz abgeben",
                "Es sind noch nicht alle Fragen beantwortet. Trotzdem abgeben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            result = self._api.submit_quiz_answers(self._session.session_id, self._selected_answers)
            QuizResultDialog(result, self).exec()
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Quiz", str(exc))


class QuizResultDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quiz-Auswertung")
        self.setMinimumSize(760, 520)
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for idx, question in enumerate(result.questions):
            box = QGroupBox(f"Frage {idx + 1}")
            box_layout = QVBoxLayout(box)
            question_label = QLabel(f"<b>{question.text}</b>")
            question_label.setWordWrap(True)
            box_layout.addWidget(question_label)
            for answer in question.answers:
                line = QLabel(answer.text)
                line.setWordWrap(True)
                if answer.is_chosen and not answer.is_correct:
                    line.setStyleSheet("background-color: #ffd6d6; padding: 4px; border-radius: 3px;")
                    line.setText(f"Deine Antwort: {answer.text}")
                elif answer.is_correct and answer.is_chosen:
                    line.setStyleSheet("background-color: #d6ffd6; padding: 4px; border-radius: 3px;")
                    line.setText(f"[OK] Deine Antwort: {answer.text}")
                elif answer.is_correct:
                    line.setStyleSheet("background-color: #d6ffd6; padding: 4px; border-radius: 3px;")
                    line.setText(f"[OK] Richtige Antwort: {answer.text}")
                box_layout.addWidget(line)
            status = QLabel("Richtig" if question.is_correct else "Falsch")
            box_layout.addWidget(status)
            content_layout.addWidget(box)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        summary = QLabel(f"<b>Ergebnis: {result.score} von {result.total} richtig.</b>")
        layout.addWidget(summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

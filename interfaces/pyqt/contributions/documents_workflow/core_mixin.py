"""Core helpers, audit, profiles, table reload (documents workflow)."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QDialog, QMessageBox

from interfaces.pyqt.contributions.common import user_to_system_role
from interfaces.pyqt.presenters.documents_detail_presenter import DocumentsDetailPresenter
from interfaces.pyqt.presenters.storage_paths import workflow_profiles_file
from interfaces.pyqt.sections.filter_bar import open_advanced_filter_dialog
from interfaces.pyqt.widgets.table_helpers import fill_table
from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
from interfaces.pyqt.workers import TableReloadResult, TableReloadWorker
from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, SystemRole, control_class_for

from .table_row import WorkflowTableRow


class DocumentsWorkflowCoreMixin:
    @staticmethod
    def _format_dt(dt: object) -> str:
        return DocumentsDetailPresenter.format_dt(dt)

    @staticmethod
    def _document_code(state: object) -> str:
        return DocumentsDetailPresenter.document_code(state)

    def _fill_two_col_table(self, table, rows: list[tuple[str, str]]) -> None:
        fill_table(table, rows)

    def _fill_history_table(self, rows: list[tuple[str, str, str, str, str]]) -> None:
        fill_table(self._tab_history, rows)

    def _append(self, title: str, payload: object, *, to_output: bool = True) -> None:
        if to_output:
            self._out.appendPlainText(f"{title}: {payload}\n")
        self._inline_notice.setText(f"Info: {title}")
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"{title}", 10000)
            except Exception:  # noqa: BLE001
                self._log.exception("Status bar update failed in _append")

    def _audit(self, *, action: str, actor: str, target: str, result: str, reason: str = "") -> None:
        self._sig_ops.audit(action=action, actor=actor, target=target, result=result, reason=reason)

    def _set_details_open(self, open_state: bool) -> None:
        self._details.set_open(open_state)

    def _is_qmb(self) -> bool:
        user = self._um.get_current_user()
        return bool(user and user_to_system_role(user) == SystemRole.QMB)

    def _apply_editor_permissions(self) -> None:
        can_edit = self._is_qmb()
        self._doc_id.setReadOnly(True)
        self._version.setReadOnly(True)
        for widget in self._metadata_inputs:
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(not can_edit)
            else:
                widget.setEnabled(can_edit)
        for widget in self._role_inputs:
            widget.setReadOnly(not can_edit)
        for button in self._metadata_buttons + self._roles_buttons:
            button.setVisible(can_edit)
            button.setEnabled(can_edit)

    def _show_error(self, exc: Exception, *, critical: bool = False) -> None:
        if critical:
            QMessageBox.critical(self, "Dokumentenlenkung", str(exc))
        else:
            QMessageBox.warning(self, "Dokumentenlenkung", str(exc))
        self._inline_notice.setText(f"Fehler: {exc}")
        self._append("ERROR", {"message": str(exc)}, to_output=False)
        window = self.window()
        if hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"FEHLER: {exc}", 10000)
            except Exception:  # noqa: BLE001
                self._log.exception("Status bar update failed in _show_error")

    def _toggle_output_visibility(self) -> None:
        visible = not self._out.isVisible()
        self._out.setVisible(visible)
        self._toggle_output_btn.setText("Protokoll ausblenden" if visible else "Protokoll anzeigen")

    def _apply_table_density(self) -> None:
        self._table.verticalHeader().setDefaultSectionSize(24)
        self._inline_notice.setText("Tabellendichte aktiv: Kompakt")

    def _is_profile_manager_allowed(self) -> bool:
        user = self._um.get_current_user()
        if user is None:
            return False
        role = user_to_system_role(user)
        if role in (SystemRole.ADMIN, SystemRole.QMB):
            return True
        if self._current_state is None:
            return False
        return str(self._current_state.owner_user_id or "") == str(user.user_id)

    def _profiles_file_path(self) -> Path:
        return workflow_profiles_file(self._container, self._app_home)

    def _doc_type_profile_rules(self) -> dict[str, dict[str, object]]:
        if not self._container.has_port("settings_service"):
            return {}
        docs_settings = self._container.get_port("settings_service").get_module_settings("documents")
        raw_rules = docs_settings.get("doc_type_profile_rules", {})
        if not isinstance(raw_rules, dict):
            return {}
        result: dict[str, dict[str, object]] = {}
        for key, value in raw_rules.items():
            if not isinstance(value, dict):
                continue
            profile_id = str(value.get("profile_id", "")).strip()
            override_possible = bool(value.get("override_possible", False))
            if not profile_id:
                continue
            result[str(key)] = {
                "profile_id": profile_id,
                "override_possible": override_possible,
            }
        return result

    def _profile_rule_for_doc_type(self, doc_type: DocumentType) -> dict[str, object]:
        rules = self._doc_type_profile_rules()
        rule = rules.get(doc_type.value, {})
        profile_id = str(rule.get("profile_id", "long_release") or "long_release")
        override_possible = bool(rule.get("override_possible", False))
        available = self._available_profiles_for_control_class(control_class_for(doc_type))
        if profile_id not in available:
            available = [profile_id, *available]
        return {
            "profile_id": profile_id,
            "override_possible": override_possible,
            "available_profiles": sorted(set(available)),
        }

    def _open_workflow_profile_manager(self) -> None:
        try:
            if not self._is_profile_manager_allowed():
                raise RuntimeError("Workflowprofil-Manager ist nur fuer Admin, QMB oder Dokumenteneigner verfuegbar")
            dialog = WorkflowProfileWizardDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = dialog.payload()
            if not payload.profile_id:
                raise RuntimeError("Profil-ID ist erforderlich")
            file_path = self._profiles_file_path()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"profiles": []}
            if file_path.exists():
                data = json.loads(file_path.read_text(encoding="utf-8"))
            profiles = list(data.get("profiles", []))
            profiles = [p for p in profiles if str(p.get("profile_id", "")) != payload.profile_id]
            profiles.append(payload.as_json_dict())
            data["profiles"] = profiles
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
            self._append("WORKFLOWPROFIL_GESPEICHERT", {"profile_id": payload.profile_id, "path": str(file_path)})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _available_profiles_for_control_class(self, control_class: ControlClass) -> list[str]:
        try:
            file_path = self._profiles_file_path()
            payload = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else {"profiles": []}
            profiles = []
            for item in payload.get("profiles", []):
                if str(item.get("control_class", "")).strip() == control_class.value:
                    profile_id = str(item.get("profile_id", "")).strip()
                    if profile_id:
                        profiles.append(profile_id)
            return sorted(set(profiles))
        except Exception:  # noqa: BLE001
            self._log.exception("Loading workflow profiles failed")
            return []

    def _apply_quick_filter(self, mode: str) -> None:
        preset = self._filter_presenter.preset(mode)
        self._scope_filter.setCurrentIndex(self._scope_filter.findData(preset.scope))
        self._status_filter.setCurrentIndex(self._status_filter.findData(preset.status_filter))
        self._reload_table()

    def _open_advanced_filter(self) -> None:
        result = open_advanced_filter_dialog(self, self._advanced_filters)
        if result is None:
            return
        self._advanced_filters = result
        self._reload_table()

    def _current_user_role(self):
        user = self._um.get_current_user()
        if user is None:
            raise RuntimeError("Anmeldung erforderlich")
        return user, user_to_system_role(user)

    def _state_from_selection(self):
        if self._current_state is None:
            raise RuntimeError("Bitte zuerst ein Dokument in der Tabelle auswaehlen")
        return getattr(self._current_state, "state", self._current_state)

    def _reload_table(self) -> None:
        if self._reload_thread is not None:
            self._reload_cancelled = True
            if self._reload_progress is not None:
                self._reload_progress.cancel()
            return
        self._reload_cancelled = False
        # Use inline notice instead of QProgressDialog to avoid noisy native WM_DESTROY
        # window lifecycle messages on some Windows setups.
        self._reload_progress = None
        self._inline_notice.setText("Tabellenaktualisierung laeuft ...")

        self._reload_thread = QThread(self)
        self._reload_worker = TableReloadWorker(self._build_reload_result)
        self._reload_worker.moveToThread(self._reload_thread)
        self._reload_thread.started.connect(self._reload_worker.run)
        self._reload_worker.finished.connect(self._on_reload_finished)
        self._reload_worker.failed.connect(self._on_reload_failed)
        self._reload_worker.finished.connect(self._cleanup_reload_worker)
        self._reload_worker.failed.connect(self._cleanup_reload_worker)
        self._reload_thread.start()

    def _cancel_reload(self) -> None:
        self._reload_cancelled = True
        self._inline_notice.setText("Tabellenaktualisierung abgebrochen.")

    def _build_reload_result(self) -> TableReloadResult:
        rows: list[object] = []
        status_filter = self._status_filter.currentData()
        statuses = list(DocumentStatus) if status_filter == "ALL" else [status_filter]
        for status in statuses:
            rows.extend(self._pool.list_by_status(status))
        registry_versions: dict[str, int | None] = {}
        if self._registry is not None:
            for row in rows:
                document_id = str(getattr(row, "document_id", "")).strip()
                if not document_id or document_id in registry_versions:
                    continue
                entry = self._registry.get_entry(document_id)
                registry_versions[document_id] = entry.active_version if entry is not None else None
        rows = [
            WorkflowTableRow(
                state=row,
                active_version=registry_versions.get(str(getattr(row, "document_id", "")).strip()),
            )
            for row in rows
        ]
        user = self._um.get_current_user()
        scope = str(self._scope_filter.currentData())
        rows = self._filter_presenter.filter_rows(
            rows,
            scope=scope,
            user_id=str(user.user_id) if user is not None else None,
            owner_contains=str(self._advanced_filters["owner_contains"]),
            title_contains=str(self._advanced_filters["title_contains"]),
            workflow_active=str(self._advanced_filters["workflow_active"]),
            active_version=str(self._advanced_filters["active_version"]),
        )
        return TableReloadResult(
            rows=rows,
            scope=scope,
            status_filter=str(status_filter),
            advanced_filters=dict(self._advanced_filters),
        )

    def _on_reload_finished(self, result: object) -> None:
        if self._reload_cancelled:
            return
        if not isinstance(result, TableReloadResult):
            self._show_error(RuntimeError("ungueltiges Reload-Ergebnis"))
            return
        self._model.load(result.rows)
        self._append(
            "TABELLE_AKTUALISIERT",
            {
                "rows": len(result.rows),
                "scope": result.scope,
                "status_filter": result.status_filter,
                "advanced": result.advanced_filters,
            },
            to_output=False,
        )
        self._update_action_visibility()

    def _on_reload_failed(self, error_message: str) -> None:
        if self._reload_cancelled:
            return
        self._show_error(RuntimeError(error_message))

    def _cleanup_reload_worker(self, *_args) -> None:
        if self._reload_progress is not None:
            self._reload_progress.close()
            self._reload_progress.deleteLater()
            self._reload_progress = None
        if self._reload_thread is not None:
            self._reload_thread.quit()
            self._reload_thread.wait(1500)
            self._reload_thread.deleteLater()
            self._reload_thread = None
        if self._reload_worker is not None:
            self._reload_worker.deleteLater()
            self._reload_worker = None


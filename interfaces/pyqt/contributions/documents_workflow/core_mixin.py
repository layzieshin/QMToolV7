"""Core helpers, audit, profile selection, table reload (documents workflow)."""
from __future__ import annotations

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QMessageBox, QDialog

from interfaces.pyqt.contributions.common import user_to_system_role
from interfaces.pyqt.presenters.documents_detail_presenter import DocumentsDetailPresenter
from interfaces.pyqt.sections.filter_bar import open_advanced_filter_dialog
from interfaces.pyqt.widgets.table_helpers import fill_table
from interfaces.pyqt.workers import TableReloadResult, TableReloadWorker
from modules.documents.api import ControlClass, DocumentStatus, DocumentType, control_class_for

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

    def _set_widgets_editable(self, widgets: list[object], allowed: bool) -> None:
        for widget in widgets:
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(not allowed)
            else:
                widget.setEnabled(allowed)

    def _gate_buttons_by_action_key(self, buttons: list[object], *, allowed_keys: set[str]) -> None:
        for button in buttons:
            key = button.property("qmtool_action_key") if hasattr(button, "property") else None
            allowed = str(key or "") in allowed_keys
            button.setVisible(allowed)
            button.setEnabled(allowed)

    def _apply_editor_permissions(self, visible_actions: set[str] | None = None) -> None:
        """Gate mutation controls by backend-derived UI keys, not local QMB role."""
        if visible_actions is None:
            user = self._um.get_current_user()
            user_id = str(user.user_id) if user is not None else None
            visible_actions = self._presenter.visible_actions_for_context(
                self._current_state,
                user_id=user_id,
                can_create_new_documents=self._can_current_user_create_documents(),
            )
        can_meta = "update_metadata" in visible_actions
        header = getattr(self, "_current_header", None)
        header_token = getattr(header, "updated_at", None) if header is not None else None
        can_header = "update_header" in visible_actions and header_token is not None
        can_roles = "assign_roles" in visible_actions
        can_cr = "change_requests" in visible_actions
        can_extend = "extend_validity" in visible_actions
        can_new_version = "new_version" in visible_actions

        self._doc_id.setReadOnly(True)
        self._version.setReadOnly(True)
        # Identity fields stay permanently readonly after create.
        self._set_widgets_editable([self._doc_type, self._control_class], False)

        metadata_field_widgets = [
            self._title,
            self._description,
            self._valid_until,
            self._next_review,
            self._custom_fields,
        ]
        header_field_widgets = [
            self._profile,
            self._department,
            self._site,
            self._regulatory_scope,
        ]
        self._set_widgets_editable(metadata_field_widgets, can_meta)
        self._set_widgets_editable(header_field_widgets, can_header)
        self._set_widgets_editable(list(self._role_inputs), can_roles)

        allowed_meta_keys = set()
        if can_meta:
            allowed_meta_keys.add("update_metadata")
        if can_header:
            allowed_meta_keys.add("update_header")
        if can_cr:
            allowed_meta_keys.add("change_requests")
        self._gate_buttons_by_action_key(self._metadata_buttons, allowed_keys=allowed_meta_keys)

        role_keys = {"assign_roles"} if can_roles else set()
        self._gate_buttons_by_action_key(self._roles_buttons, allowed_keys=role_keys)

        extension_keys = set()
        if can_extend:
            extension_keys.add("extend_validity")
        if can_new_version:
            extension_keys.add("new_version")
        self._gate_buttons_by_action_key(
            getattr(self, "_extension_buttons", []),
            allowed_keys=extension_keys,
        )

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

    def _is_profile_manager_allowed(self) -> bool:
        """Whether the profile-manager action may be shown for the current user.

        GUI editing remains CLI-only; this only gates button visibility/enablement.
        """
        user = self._um.get_current_user()
        if user is None:
            return False
        get_capabilities = getattr(getattr(self, "_pool", None), "get_capabilities", None)
        if callable(get_capabilities):
            capabilities = get_capabilities()
            if isinstance(capabilities, dict):
                return capabilities.get("can_administer_workflow_profiles") is True
        return False

    def _open_workflow_profile_manager(self) -> None:
        from interfaces.pyqt.widgets.workflow_profile_wizard import WorkflowProfileWizardDialog
        from modules.documents.api import DocumentStatus

        dialog = WorkflowProfileWizardDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        wizard = dialog.payload()
        transitions: list[dict[str, object]] = []
        transition_no = 1
        if DocumentStatus.IN_REVIEW in wizard.phases:
            transitions.append(
                {
                    "transition_no": transition_no,
                    "from_status": "DRAFT",
                    "to_status": "IN_REVIEW",
                    "required_role": "EDITOR",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": "IN_PROGRESS->IN_REVIEW" in wizard.signature_required_transitions,
                    "four_eyes_required": wizard.four_eyes_required,
                }
            )
            transition_no += 1
            transitions.append(
                {
                    "transition_no": transition_no,
                    "from_status": "IN_REVIEW",
                    "to_status": "IN_APPROVAL" if DocumentStatus.IN_APPROVAL in wizard.phases else "APPROVED",
                    "required_role": "REVIEWER",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": False,
                    "four_eyes_required": wizard.four_eyes_required,
                }
            )
            transition_no += 1
        if DocumentStatus.IN_APPROVAL in wizard.phases:
            transitions.append(
                {
                    "transition_no": transition_no,
                    "from_status": "IN_APPROVAL",
                    "to_status": "APPROVED",
                    "required_role": "APPROVER",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": "IN_APPROVAL->APPROVED" in wizard.signature_required_transitions,
                    "four_eyes_required": wizard.four_eyes_required,
                }
            )
        payload = {
            "profile_code": wizard.profile_id,
            "label": wizard.label,
            "control_class": wizard.control_class.value,
            "requires_editors": wizard.requires_editors,
            "requires_reviewers": wizard.requires_reviewers,
            "requires_approvers": wizard.requires_approvers,
            "allows_content_changes": True,
            "release_evidence_mode": "WORKFLOW",
            "transitions": transitions,
        }
        try:
            operation = wizard.operation
            reason = wizard.change_reason
            if operation == "create":
                created = self._wf.create_workflow_profile_definition(payload, change_reason=reason)
                event = "WORKFLOWPROFIL_ERSTELLT"
            elif operation == "create_version":
                created = self._wf.create_workflow_profile_version(wizard.profile_id, payload, change_reason=reason)
                event = "WORKFLOWPROFIL_VERSION_ERSTELLT"
            elif operation == "activate":
                created = self._wf.activate_workflow_profile_definition(wizard.profile_id, change_reason=reason)
                event = "WORKFLOWPROFIL_AKTIVIERT"
            elif operation == "deactivate":
                created = self._wf.deactivate_workflow_profile_definition(wizard.profile_id, change_reason=reason)
                event = "WORKFLOWPROFIL_DEAKTIVIERT"
            else:
                created = self._wf.bind_document_type_default_profile(
                    wizard.doc_type.value, wizard.profile_id, change_reason=reason
                )
                event = "WORKFLOWPROFIL_DOKUMENTTYP_GEBUNDEN"
            self._append(event, created)
            QMessageBox.information(
                self,
                "Workflowprofil",
                f"Profilaktion für '{created.get('profile_code', wizard.profile_id)}' wurde ausgeführt.",
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _available_profiles_for_control_class(self, control_class: ControlClass) -> list[str]:
        try:
            return self._wf.list_profile_ids_for_control_class(control_class)
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

        # Snapshot UI state on the GUI thread — never touch QWidgets from the worker.
        status_filter = self._status_filter.currentData()
        scope = str(self._scope_filter.currentData())
        advanced_filters = dict(self._advanced_filters)

        self._reload_thread = QThread(self)
        self._reload_worker = TableReloadWorker(
            lambda: self._build_reload_result(
                status_filter=status_filter,
                scope=scope,
                advanced_filters=advanced_filters,
            )
        )
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

    def _build_reload_result(
        self,
        *,
        status_filter: object,
        scope: str,
        advanced_filters: dict[str, object],
    ) -> TableReloadResult:
        rows: list[object] = []
        statuses = list(DocumentStatus) if status_filter == "ALL" else [status_filter]
        for status in statuses:
            try:
                rows.extend(self._pool.list_by_status(status))
            except Exception as exc:  # noqa: BLE001
                # Fail-closed M0 / missing session token must not kill the worker thread.
                raise RuntimeError(str(exc)) from exc
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
        rows = self._filter_presenter.filter_rows(
            rows,
            scope=scope,
            user_id=str(user.user_id) if user is not None else None,
            owner_contains=str(advanced_filters["owner_contains"]),
            title_contains=str(advanced_filters["title_contains"]),
            workflow_active=str(advanced_filters["workflow_active"]),
            active_version=str(advanced_filters["active_version"]),
        )
        return TableReloadResult(
            rows=rows,
            scope=scope,
            status_filter=str(status_filter),
            advanced_filters=dict(advanced_filters),
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


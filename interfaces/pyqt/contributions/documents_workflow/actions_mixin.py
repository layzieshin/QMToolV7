"""Workflow actions: import, transitions, metadata (documents workflow)."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QThread, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
)

from interfaces.pyqt.contributions.common import parse_csv_set, user_to_system_role
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from interfaces.pyqt.presenters.storage_paths import artifacts_root
from interfaces.pyqt.widgets.document_create_wizard import DocumentCreateWizard
from interfaces.pyqt.widgets.reject_reason_dialog import RejectReasonDialog
from interfaces.pyqt.widgets.validity_extension_dialog import ValidityExtensionDialog
from interfaces.pyqt.widgets.workflow_start_wizard import WorkflowStartWizard
from interfaces.pyqt.workers.docx_conversion_worker import DocxConversionWorker
from modules.documents.contracts import ArtifactType, DocumentStatus, DocumentType, SystemRole, ValidityExtensionOutcome, control_class_for


class DocumentsWorkflowActionsMixin:
    def _add_change_request(self) -> None:
        try:
            state = self._state_from_selection()
            user, role = self._current_user_role()
            dialog = QDialog(self)
            dialog.setWindowTitle("Change Request hinzufügen")
            change_id = QLineEdit()
            reason = QLineEdit()
            impact_refs = QLineEdit()
            form = QFormLayout()
            form.addRow("Change-ID", change_id)
            form.addRow("Grund", reason)
            form.addRow("Impact-Refs (CSV)", impact_refs)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout = QVBoxLayout(dialog)
            layout.addLayout(form)
            layout.addWidget(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = self._wf.add_change_request(
                state,
                change_id=change_id.text().strip(),
                reason=reason.text().strip(),
                impact_refs=[value.strip() for value in impact_refs.text().split(",") if value.strip()],
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("CHANGE_REQUEST_GESPEICHERT", {"document_id": payload.document_id, "version": payload.version})
            self._current_state = payload
            self._refresh_details()
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _export_change_requests(self) -> None:
        try:
            state = self._state_from_selection()
            rows = self._wf.list_change_requests(state)
            if not rows:
                self._inline_notice.setText("Keine Change Requests zum Export vorhanden.")
                return
            default_suffix = ".csv" if self._last_change_export_format == "csv" else ".json"
            default_name = f"{state.document_id}_v{state.version}_change_requests{default_suffix}"
            default_target = self._last_change_export_dir / default_name
            selected_filter_default = (
                "CSV (*.csv)" if self._last_change_export_format == "csv" else "JSON (*.json)"
            )
            target, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Change Requests exportieren",
                str(default_target),
                "JSON (*.json);;CSV (*.csv)",
                selected_filter_default,
            )
            if not target:
                return
            output = Path(target)
            output.parent.mkdir(parents=True, exist_ok=True)
            export_csv = selected_filter.lower().startswith("csv") or output.suffix.lower() == ".csv"
            if export_csv:
                if output.suffix.lower() != ".csv":
                    output = output.with_suffix(".csv")
                with output.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(
                        fh,
                        fieldnames=["change_id", "reason", "impact_refs", "created_by", "created_at"],
                    )
                    writer.writeheader()
                    for row in rows:
                        refs = row.get("impact_refs", [])
                        writer.writerow(
                            {
                                "change_id": str(row.get("change_id", "")),
                                "reason": str(row.get("reason", "")),
                                "impact_refs": ",".join(str(v) for v in refs) if isinstance(refs, list) else "",
                                "created_by": str(row.get("created_by", "")),
                                "created_at": str(row.get("created_at", "")),
                            }
                        )
                fmt = "csv"
            else:
                if output.suffix.lower() != ".json":
                    output = output.with_suffix(".json")
                output.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")
                fmt = "json"
            self._last_change_export_dir = output.parent
            self._last_change_export_format = fmt
            self._append("CHANGE_REQUEST_EXPORT", {"format": fmt, "path": str(output), "count": len(rows)})
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _new_import(self) -> None:
        try:
            if not self._can_current_user_create_documents():
                raise RuntimeError(
                    "Du darfst keine neuen Dokumente anlegen. "
                    "Bitte Admin-Freigabe in Einstellungen > Dokumentenlenkung > CanCreateNewDocuments setzen."
                )
            users = self._um.list_users()
            user = self._um.get_current_user()
            default_owner = user.user_id if user is not None else ""
            current_role = user_to_system_role(user) if user is not None else None
            can_override_profiles = current_role in {SystemRole.QMB, SystemRole.ADMIN}
            profile_rules = {
                dt.value: self._profile_rule_for_doc_type(dt)
                for dt in DocumentType
            }
            dlg = DocumentCreateWizard(
                [u.user_id for u in users],
                default_owner,
                profile_rules=profile_rules,
                can_override_profiles=can_override_profiles,
                parent=self,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            data = dlg.payload()
            if not data.document_id:
                raise RuntimeError("Dokumentenkennung ist erforderlich")
            version = 1
            document_id = data.document_id.strip()
            type_rule = self._profile_rule_for_doc_type(data.doc_type)
            effective_profile_id = str(type_rule.get("profile_id", "long_release"))
            if can_override_profiles and bool(type_rule.get("override_possible", False)):
                selected = data.workflow_profile_id.strip()
                if selected:
                    effective_profile_id = selected
            created = self._wf.create_document_version(
                document_id,
                version,
                owner_user_id=data.owner_user_id or default_owner or None,
                title=data.title,
                description=data.description or None,
                doc_type=data.doc_type,
                control_class=control_class_for(data.doc_type),
                workflow_profile_id=effective_profile_id,
            )
            self._append("WIZARD_DRAFT", created)
            if not dlg.create_draft_only():
                user_obj, role = self._current_user_role()
                if data.mode == "template":
                    self._append(
                        "WIZARD_TEMPLATE",
                        self._wf.create_from_template(
                            document_id,
                            version,
                            Path(data.source_path),
                            actor_user_id=user_obj.user_id,
                            actor_role=role,
                        ),
                    )
                elif data.mode == "docx":
                    self._append(
                        "WIZARD_IMPORT_DOCX",
                        self._wf.import_existing_docx(
                            document_id,
                            version,
                            Path(data.source_path),
                            actor_user_id=user_obj.user_id,
                            actor_role=role,
                        ),
                    )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _edit_docx(self) -> None:
        try:
            state = self._state_from_selection()
            post_edit_statuses = {
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
                DocumentStatus.APPROVED,
                DocumentStatus.ARCHIVED,
            }
            if state.status in post_edit_statuses:
                priorities = DocumentsWorkflowPresenter.default_artifact_priority(state.status)
                for artifact_type in priorities:
                    if self._sig_ops.open_artifact(state, artifact_type):
                        self._append(
                            "PDF_GEOEFFNET",
                            {"reason": "post-edit phase – DOCX gesperrt", "type": artifact_type.value},
                        )
                        return
                raise RuntimeError(
                    f"Status ist '{state.status.value}' – DOCX ist gesperrt. "
                    "Keine PDF-Datei für diese Phase gefunden."
                )
            if not self._sig_ops.open_artifact(state, ArtifactType.SOURCE_DOCX):
                raise RuntimeError("Kein lokaler DOCX-Pfad im Artefakt verfuegbar")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _start_workflow(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            users = self._um.list_users()
            wizard = WorkflowStartWizard(
                self._profile.text().strip() or state.workflow_profile_id,
                profile_ids=self._available_profiles_for_control_class(state.control_class),
                available_user_ids=[u.user_id for u in users],
                current_editors=set(state.assignments.editors),
                current_reviewers=set(state.assignments.reviewers),
                current_approvers=set(state.assignments.approvers),
                parent=self,
            )
            if wizard.exec() != QDialog.DialogCode.Accepted:
                return
            cfg = wizard.payload()
            profile = self._docs_service.get_profile(cfg.profile_id)
            desired_editors = cfg.editors if cfg.editors else set(state.assignments.editors)
            desired_reviewers = cfg.reviewers if cfg.reviewers else set(state.assignments.reviewers)
            desired_approvers = cfg.approvers if cfg.approvers else set(state.assignments.approvers)
            if (
                desired_editors != set(state.assignments.editors)
                or desired_reviewers != set(state.assignments.reviewers)
                or desired_approvers != set(state.assignments.approvers)
            ):
                state = self._wf.assign_workflow_roles(
                    state,
                    editors=desired_editors,
                    reviewers=desired_reviewers,
                    approvers=desired_approvers,
                    actor_user_id=user.user_id,
                    actor_role=role,
                )
                self._append("ROLLEN_GESPEICHERT", state)
            payload = self._wf.start_workflow(state, profile, actor_user_id=user.user_id, actor_role=role)
            self._append("WORKFLOW_GESTARTET", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc, critical=True)

    def _complete_editing(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            # Avoid blocking DOCX->PDF conversion on GUI thread.
            pdf_path = self._sig_ops.find_pdf_for_signature_sync(
                state,
                transition="IN_PROGRESS->IN_REVIEW",
                allow_docx_fallback=False,
            )
            if pdf_path is None:
                docx_path = self._sig_ops.find_docx_source_for_signature(state)
                if docx_path is not None:
                    self._convert_docx_for_signature(docx_path)
            self._wf.ensure_source_pdf_for_signing(state, actor_user_id=user.user_id, actor_role=role)
            self._audit(
                action="documents.workflow.editing.prepare_pdf",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="complete_editing",
            )
            sign_request = self._sig_ops.build_sign_request_or_none(state, "IN_PROGRESS->IN_REVIEW", self)
            if self._state_from_selection().workflow_profile and "IN_PROGRESS->IN_REVIEW" in set(
                self._state_from_selection().workflow_profile.signature_required_transitions
            ) and sign_request is None:
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                self._audit(
                    action="documents.workflow.editing.complete",
                    actor=str(user.user_id),
                    target=f"{state.document_id}:{state.version}",
                    result="cancelled",
                    reason="signature_cancelled",
                )
                return
            payload = self._wf.complete_editing(
                self._state_from_selection(),
                sign_request=sign_request,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("PHASE_ABGESCHLOSSEN", payload)
            self._audit(
                action="documents.workflow.editing.complete",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="IN_PROGRESS->IN_REVIEW",
            )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            try:
                state = self._state_from_selection()
                actor = "system"
                if 'user' in locals() and user is not None:
                    actor = str(getattr(user, "user_id", "system"))
                self._audit(
                    action="documents.workflow.editing.complete",
                    actor=actor,
                    target=f"{state.document_id}:{state.version}",
                    result="error",
                    reason=str(exc),
                )
            except Exception:  # noqa: BLE001
                self._log.exception("Audit write failed after complete_editing exception")
            self._show_error(exc)

    def _convert_docx_for_signature(self, docx_path: Path) -> None:
        worker_thread = QThread(self)
        worker = DocxConversionWorker(self._sig_ops.convert_docx_to_temp_pdf, docx_path)
        worker.moveToThread(worker_thread)
        loop = QEventLoop(self)
        result: dict[str, object] = {"path": None, "error": None}

        def _on_finished(path_obj: object) -> None:
            result["path"] = path_obj
            loop.quit()

        def _on_failed(error_message: str) -> None:
            result["error"] = error_message
            loop.quit()

        worker_thread.started.connect(worker.run)
        worker.finished.connect(_on_finished)
        worker.failed.connect(_on_failed)
        worker.finished.connect(worker_thread.quit)
        worker.failed.connect(worker_thread.quit)
        progress = QProgressDialog("DOCX wird fuer Signatur nach PDF konvertiert ...", None, 0, 0, self)
        progress.setWindowTitle("Dokumentenlenkung")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        worker_thread.start()
        progress.show()
        loop.exec()
        progress.close()
        worker_thread.wait(3000)
        worker.deleteLater()
        worker_thread.deleteLater()
        if result["error"] is not None:
            raise RuntimeError(str(result["error"]))

    def _abort_workflow(self) -> None:
        try:
            dlg = RejectReasonDialog("Workflow abbrechen", "Grund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.abort_workflow(
                self._state_from_selection(),
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append(
                "WORKFLOW_ABGEBROCHEN",
                {"result": payload, "dialog_reason": dlg.reason()},
            )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _review_accept(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            sign_request = self._sig_ops.build_sign_request_or_none(state, "IN_REVIEW->IN_APPROVAL", self)
            if (
                state.workflow_profile
                and "IN_REVIEW->IN_APPROVAL" in set(state.workflow_profile.signature_required_transitions)
                and sign_request is None
            ):
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                self._audit(
                    action="documents.workflow.review.accept",
                    actor=str(user.user_id),
                    target=f"{state.document_id}:{state.version}",
                    result="cancelled",
                    reason="signature_cancelled",
                )
                return
            payload = self._wf.accept_review(
                self._state_from_selection(),
                user.user_id,
                sign_request=sign_request,
                actor_role=role,
            )
            self._append("PRUEFUNG_ANGENOMMEN", payload)
            self._audit(
                action="documents.workflow.review.accept",
                actor=str(user.user_id),
                target=f"{state.document_id}:{state.version}",
                result="ok",
                reason="IN_REVIEW->IN_APPROVAL",
            )
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _review_reject(self) -> None:
        try:
            dlg = RejectReasonDialog("Pruefung ablehnen", "Ablehnungsgrund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.reject_review(self._state_from_selection(), user.user_id, dlg.reason(), actor_role=role)
            self._append("PRUEFUNG_ABGELEHNT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _approval_accept(self) -> None:
        try:
            confirm = QMessageBox.question(
                self,
                "Freigabe annehmen",
                "Freigabe wirklich annehmen? Optional wird die konfigurierte Signaturanforderung ausgefuehrt.",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            user, role = self._current_user_role()
            sign_request = self._sig_ops.build_sign_request_or_none(self._state_from_selection(), "IN_APPROVAL->APPROVED", self)
            if self._state_from_selection().workflow_profile and "IN_APPROVAL->APPROVED" in set(
                self._state_from_selection().workflow_profile.signature_required_transitions
            ) and sign_request is None:
                self._inline_notice.setText("Signaturvorgang abgebrochen.")
                return
            payload = self._wf.accept_approval(
                self._state_from_selection(),
                user.user_id,
                sign_request=sign_request,
                actor_role=role,
            )
            self._append("FREIGABE_ANGENOMMEN", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _approval_reject(self) -> None:
        try:
            dlg = RejectReasonDialog("Freigabe ablehnen", "Ablehnungsgrund", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            user, role = self._current_user_role()
            payload = self._wf.reject_approval(self._state_from_selection(), user.user_id, dlg.reason(), actor_role=role)
            self._append("FREIGABE_ABGELEHNT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _archive_approved(self) -> None:
        try:
            confirm = QMessageBox.question(
                self,
                "Archivieren",
                "Dokumentversion wirklich archivieren?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            user, role = self._current_user_role()
            payload = self._wf.archive_approved(
                self._state_from_selection(),
                actor_role=role,
                actor_user_id=user.user_id,
            )
            self._append("DOKUMENT_ARCHIVIERT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _assign_roles(self) -> None:
        try:
            user, role = self._current_user_role()
            payload = self._wf.assign_workflow_roles(
                self._state_from_selection(),
                editors=parse_csv_set(self._editors.text()),
                reviewers=parse_csv_set(self._reviewers.text()),
                approvers=parse_csv_set(self._approvers.text()),
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("ROLLEN_GESPEICHERT", payload)
            self._refresh_details()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _update_metadata(self) -> None:
        try:
            user, role = self._current_user_role()
            valid_until = datetime.fromisoformat(self._valid_until.text().strip()) if self._valid_until.text().strip() else None
            next_review = datetime.fromisoformat(self._next_review.text().strip()) if self._next_review.text().strip() else None
            custom_fields = json.loads(self._custom_fields.text().strip() or "{}")
            payload = self._wf.update_version_metadata(
                self._state_from_selection(),
                title=self._title.text().strip() or None,
                description=self._description.text().strip() or None,
                valid_until=valid_until,
                next_review_at=next_review,
                custom_fields=custom_fields,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("METADATEN_GESPEICHERT", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _update_header(self) -> None:
        try:
            user, role = self._current_user_role()
            state = self._state_from_selection()
            payload = self._wf.update_document_header(
                state.document_id,
                doc_type=self._doc_type.currentData(),
                control_class=self._control_class.currentData(),
                workflow_profile_id=self._profile.text().strip() or None,
                department=self._department.text().strip() or None,
                site=self._site.text().strip() or None,
                regulatory_scope=self._regulatory_scope.text().strip() or None,
                actor_user_id=user.user_id,
                actor_role=role,
            )
            self._append("HEADER_GESPEICHERT", payload)
            self._refresh_details()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _extend_validity(self) -> None:
        try:
            state = self._state_from_selection()
            user, _role = self._current_user_role()

            if state.status != DocumentStatus.APPROVED:
                raise RuntimeError("Verlaengerung ist nur im Status APPROVED moeglich")
            if state.extension_count >= 3:
                raise RuntimeError("Maximale Anzahl von Verlaengerungen (3) erreicht")
            dialog = ValidityExtensionDialog(
                valid_from=state.valid_from,
                valid_until=state.valid_until,
                next_review_at=state.next_review_at,
                extension_count=state.extension_count,
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return
            request = dialog.payload()
            if request.review_outcome == ValidityExtensionOutcome.NEW_VERSION_REQUIRED:
                self._inline_notice.setText("Neue Version erforderlich - Verlaengerung nicht ausgefuehrt.")
                return

            sign_request = self._sig_ops.build_extension_sign_request(state, self)
            if sign_request is None:
                self._inline_notice.setText("Verlaengerungsvorgang abgebrochen.")
                return

            self._sig_ops.require_signature_call(sign_request)
            signing_user_id = str(sign_request.signer_user or user.user_id)

            payload, is_maxed = self._wf.extend_annual_validity(
                state,
                actor_user_id=signing_user_id,
                signature_present=True,
                duration_days=request.duration_days,
                reason=request.reason,
                review_outcome=request.review_outcome,
            )
            self._append("JAHRESVERLAENGERUNG", {
                "new_extension_count": payload.extension_count,
                "is_maxed": is_maxed,
                "review_outcome": request.review_outcome.value,
                "reason": request.reason,
                "next_review_at": str(payload.next_review_at),
                "valid_until": str(payload.valid_until),
            })
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _new_version_after_archive(self) -> None:
        try:
            payload = self._wf.create_new_version_after_archive(
                self._state_from_selection(),
                int(self._next_version.text().strip()),
            )
            self._append("NEUE_VERSION_NACH_ARCHIV", payload)
            self._reload_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _resolve_artifacts_root(self) -> Path:
        return artifacts_root(self._container, self._app_home)

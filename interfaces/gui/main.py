# ──────────────────────────────────────────────────────────────────────
# LEGACY FROZEN — no new code.
# This Tk-based GUI is superseded by the PyQt interface.
# Boundary violations (direct imports from modules.*.errors) are
# accepted and will NOT be fixed. See ARCHITECTURE_REFACTOR_CANONICAL.md
# Phase 6.
# ──────────────────────────────────────────────────────────────────────
from __future__ import annotations

import argparse
import json
import os
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import ttk
import uuid

from modules.documents.contracts import DocumentStatus, RejectionReason, SystemRole
from modules.documents.errors import DocumentWorkflowError
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from modules.signature.errors import SignatureError
from qm_platform.runtime.bootstrap import register_core_modules

from interfaces.cli.bootstrap import build_container


def _role_to_system_role(role: str) -> SystemRole:
    mapping = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    try:
        return mapping[role]
    except KeyError as exc:
        raise RuntimeError(f"unsupported role '{role}'") from exc


class UiController:
    def __init__(self) -> None:
        self.container = build_container()
        self.lifecycle = register_core_modules(self.container)
        self.lifecycle.start()
        self.usermanagement = self.container.get_port("usermanagement_service")
        self.documents_service = self.container.get_port("documents_service")
        self.documents_pool_api = self.container.get_port("documents_pool_api")
        self.documents_workflow_api = self.container.get_port("documents_workflow_api")
        self.settings_service = self.container.get_port("settings_service")

    def current_user(self):
        return self.usermanagement.get_current_user()

    def login(self, username: str, password: str):
        user = self.usermanagement.login(username, password)
        if user is None:
            raise RuntimeError("invalid credentials")
        return user

    def logout(self) -> None:
        self.usermanagement.logout()

    def list_pool(self, status: DocumentStatus) -> list[dict]:
        rows = self.documents_pool_api.list_by_status(status)
        return [{"document_id": row.document_id, "version": row.version, "status": row.status.value} for row in rows]

    def get_document(self, document_id: str, version: int):
        state = self.documents_service.get_document_version(document_id, version)
        if state is None:
            raise RuntimeError(f"document version not found: {document_id} v{version}")
        return state

    def create_document_version(self, document_id: str, version: int):
        current_user = self._require_user()
        return self.documents_service.create_document_version(document_id, version, owner_user_id=current_user.user_id)

    def assign_roles(self, document_id: str, version: int, editors: set[str], reviewers: set[str], approvers: set[str]):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.assign_workflow_roles(
            state,
            editors=editors,
            reviewers=reviewers,
            approvers=approvers,
            actor_user_id=current_user.user_id,
            actor_role=current_role,
        )

    def start_workflow(self, document_id: str, version: int, profile_id: str = "long_release"):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        profile = self.documents_service.get_profile(profile_id)
        return self.documents_workflow_api.start_workflow(
            state,
            profile,
            actor_user_id=current_user.user_id,
            actor_role=current_role,
        )

    def complete_editing(self, document_id: str, version: int, sign_request: object | None = None):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.complete_editing(
            state,
            sign_request=sign_request,
            actor_user_id=current_user.user_id,
            actor_role=current_role,
        )

    def review_accept(self, document_id: str, version: int, sign_request: object | None = None):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.accept_review(
            state,
            current_user.user_id,
            sign_request=sign_request,
            actor_role=current_role,
        )

    def review_reject(self, document_id: str, version: int, reason_text: str):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        reason = RejectionReason(template_text=reason_text, free_text=None)
        return self.documents_workflow_api.reject_review(state, current_user.user_id, reason, actor_role=current_role)

    def approval_accept(self, document_id: str, version: int, sign_request: object | None = None):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.accept_approval(
            state,
            current_user.user_id,
            sign_request=sign_request,
            actor_role=current_role,
        )

    def approval_reject(self, document_id: str, version: int, reason_text: str):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        reason = RejectionReason(template_text=reason_text, free_text=None)
        return self.documents_workflow_api.reject_approval(state, current_user.user_id, reason, actor_role=current_role)

    def abort_workflow(self, document_id: str, version: int):
        current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.abort_workflow(
            state,
            actor_user_id=current_user.user_id,
            actor_role=current_role,
        )

    def archive(self, document_id: str, version: int):
        _current_user, current_role = self._require_user_and_role()
        state = self.get_document(document_id, version)
        return self.documents_workflow_api.archive_approved(state, current_role)

    def list_settings_modules(self) -> list[str]:
        self._require_user()
        return self.settings_service.registry.list_module_ids()

    def get_settings(self, module_id: str) -> dict:
        self._require_user()
        return self.settings_service.get_module_settings(module_id)

    def set_settings(self, module_id: str, values: dict) -> dict:
        _current_user, current_role = self._require_user_and_role()
        if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
            raise RuntimeError("only QMB or ADMIN may set settings")
        payload = dict(values)
        acknowledge = bool(payload.pop("_acknowledge_governance_change", False))
        self.settings_service.set_module_settings(
            module_id,
            payload,
            acknowledge_governance_change=acknowledge,
        )
        return self.settings_service.get_module_settings(module_id)

    def list_users(self) -> list[dict]:
        _current_user, current_role = self._require_user_and_role()
        if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
            raise RuntimeError("only QMB or ADMIN may list users")
        rows = self.usermanagement.list_users()
        return [{"user_id": row.user_id, "username": row.username, "role": row.role} for row in rows]

    def create_user(self, username: str, password: str, role: str) -> dict:
        _current_user, current_role = self._require_user_and_role()
        if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
            raise RuntimeError("only QMB or ADMIN may create users")
        user = self.usermanagement.create_user(username, password, role)
        return {"user_id": user.user_id, "username": user.username, "role": user.role}

    def _require_user(self):
        user = self.current_user()
        if user is None:
            raise RuntimeError("login required")
        return user

    def _require_user_and_role(self):
        user = self._require_user()
        return user, _role_to_system_role(user.role)


class QmToolGui(tk.Tk):
    def __init__(self, controller: UiController) -> None:
        super().__init__()
        self.controller = controller
        self.title("QmTool V4 - UI MVP")
        self.geometry("980x700")
        self.output_window: tk.Toplevel | None = None
        self.output_popout: tk.Text | None = None

        self._build_login_bar()
        self._build_tabs()
        self._refresh_user_label()

    def _build_login_bar(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(frame, text="Username").pack(side=tk.LEFT)
        self.username_entry = ttk.Entry(frame, width=14)
        self.username_entry.pack(side=tk.LEFT, padx=(6, 10))
        self.username_entry.insert(0, "admin")

        ttk.Label(frame, text="Password").pack(side=tk.LEFT)
        self.password_entry = ttk.Entry(frame, width=14, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=(6, 10))
        self.password_entry.insert(0, "admin")

        ttk.Button(frame, text="Login", command=self._on_login).pack(side=tk.LEFT, padx=4)
        ttk.Button(frame, text="Logout", command=self._on_logout).pack(side=tk.LEFT, padx=4)
        self.output_toggle_btn = ttk.Button(frame, text="Output Popout", command=self._toggle_output_window)
        self.output_toggle_btn.pack(side=tk.LEFT, padx=4)

        self.user_label = ttk.Label(frame, text="Current user: -")
        self.user_label.pack(side=tk.LEFT, padx=14)

    def _build_tabs(self) -> None:
        pane = ttk.Panedwindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        top = ttk.Frame(pane)
        bottom = ttk.Frame(pane)
        pane.add(top, weight=4)
        pane.add(bottom, weight=1)

        notebook = ttk.Notebook(top)
        notebook.pack(fill=tk.BOTH, expand=True)

        documents_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        users_tab = ttk.Frame(notebook)
        notebook.add(documents_tab, text="Documents")
        notebook.add(settings_tab, text="Settings")
        notebook.add(users_tab, text="Users")

        self._build_documents_tab(documents_tab)
        self._build_settings_tab(settings_tab)
        self._build_users_tab(users_tab)

        output_header = ttk.Frame(bottom)
        output_header.pack(fill=tk.X)
        ttk.Label(output_header, text="Output (persistent)").pack(side=tk.LEFT, padx=4, pady=2)
        ttk.Button(output_header, text="Clear", command=self._clear_output).pack(side=tk.RIGHT, padx=4, pady=2)

        self.output = tk.Text(bottom, wrap=tk.WORD, height=10)
        self.output.pack(fill=tk.BOTH, expand=True)

    def _build_documents_tab(self, parent: ttk.Frame) -> None:
        frm = ttk.Frame(parent)
        frm.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(frm, text="Document ID").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.doc_id_entry = ttk.Entry(frm, width=24)
        self.doc_id_entry.grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        ttk.Label(frm, text="Version").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        self.doc_version_entry = ttk.Entry(frm, width=8)
        self.doc_version_entry.grid(row=0, column=3, sticky=tk.W, padx=4, pady=4)
        self.doc_version_entry.insert(0, "1")
        ttk.Label(frm, text="Profile").grid(row=0, column=4, sticky=tk.W, padx=4, pady=4)
        self.profile_entry = ttk.Entry(frm, width=16)
        self.profile_entry.grid(row=0, column=5, sticky=tk.W, padx=4, pady=4)
        self.profile_entry.insert(0, "long_release")

        sign = ttk.Frame(parent)
        sign.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(sign, text="Sign Input PDF").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.sign_input_entry = ttk.Entry(sign, width=24)
        self.sign_input_entry.grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        ttk.Label(sign, text="Sign Output PDF").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        self.sign_output_entry = ttk.Entry(sign, width=24)
        self.sign_output_entry.grid(row=0, column=3, sticky=tk.W, padx=4, pady=4)
        ttk.Label(sign, text="Sign PNG").grid(row=0, column=4, sticky=tk.W, padx=4, pady=4)
        self.sign_png_entry = ttk.Entry(sign, width=24)
        self.sign_png_entry.grid(row=0, column=5, sticky=tk.W, padx=4, pady=4)
        ttk.Label(sign, text="Signer Password").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        self.sign_password_entry = ttk.Entry(sign, width=18, show="*")
        self.sign_password_entry.grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)

        roles = ttk.Frame(parent)
        roles.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(roles, text="Editors").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.editors_entry = ttk.Entry(roles, width=18)
        self.editors_entry.grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        self.editors_entry.insert(0, "admin")
        ttk.Label(roles, text="Reviewers").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        self.reviewers_entry = ttk.Entry(roles, width=18)
        self.reviewers_entry.grid(row=0, column=3, sticky=tk.W, padx=4, pady=4)
        self.reviewers_entry.insert(0, "qmb")
        ttk.Label(roles, text="Approvers").grid(row=0, column=4, sticky=tk.W, padx=4, pady=4)
        self.approvers_entry = ttk.Entry(roles, width=18)
        self.approvers_entry.grid(row=0, column=5, sticky=tk.W, padx=4, pady=4)
        self.approvers_entry.insert(0, "admin")

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X, padx=8, pady=8)
        for idx, (label, handler) in enumerate(
            [
                ("Create Version", self._on_create_version),
                ("Assign Roles", self._on_assign_roles),
                ("Start Workflow", self._on_start_workflow),
                ("Complete Editing", self._on_complete_editing),
                ("Review Accept", self._on_review_accept),
                ("Approval Accept", self._on_approval_accept),
                ("Abort Workflow", self._on_abort_workflow),
                ("Archive", self._on_archive),
                ("Load Details", self._on_load_details),
                ("Pool List (PLANNED)", self._on_pool_list),
            ]
        ):
            ttk.Button(actions, text=label, command=handler).grid(row=0, column=idx, padx=3, pady=4)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        frm = ttk.Frame(parent)
        frm.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(frm, text="Module").grid(row=0, column=0, padx=4, pady=4)
        self.settings_module_entry = ttk.Entry(frm, width=20)
        self.settings_module_entry.grid(row=0, column=1, padx=4, pady=4)
        self.settings_module_entry.insert(0, "documents")
        ttk.Button(frm, text="List Modules", command=self._on_settings_list_modules).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(frm, text="Get Settings", command=self._on_settings_get).grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(frm, text="Set Settings JSON", command=self._on_settings_set).grid(row=0, column=4, padx=4, pady=4)

        ttk.Label(parent, text="Settings JSON").pack(anchor=tk.W, padx=12)
        self.settings_json = tk.Text(parent, height=8)
        self.settings_json.pack(fill=tk.BOTH, expand=False, padx=8, pady=8)
        self.settings_json.insert("1.0", '{"default_profile_id":"long_release","allow_custom_profiles":true,"profiles_file":"modules/documents/workflow_profiles.json","documents_db_path":"storage/documents/documents.db","artifacts_root":"storage/documents/artifacts"}')

    def _build_users_tab(self, parent: ttk.Frame) -> None:
        frm = ttk.Frame(parent)
        frm.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(frm, text="Username").grid(row=0, column=0, padx=4, pady=4)
        self.new_user_entry = ttk.Entry(frm, width=18)
        self.new_user_entry.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm, text="Password").grid(row=0, column=2, padx=4, pady=4)
        self.new_password_entry = ttk.Entry(frm, width=18, show="*")
        self.new_password_entry.grid(row=0, column=3, padx=4, pady=4)
        ttk.Label(frm, text="Role").grid(row=0, column=4, padx=4, pady=4)
        self.new_role = ttk.Combobox(frm, values=["Admin", "QMB", "User"], width=8, state="readonly")
        self.new_role.grid(row=0, column=5, padx=4, pady=4)
        self.new_role.set("User")
        ttk.Button(frm, text="Create User", command=self._on_create_user).grid(row=0, column=6, padx=4, pady=4)
        ttk.Button(frm, text="List Users", command=self._on_list_users).grid(row=0, column=7, padx=4, pady=4)

    def _doc_ref(self) -> tuple[str, int]:
        document_id = self.doc_id_entry.get().strip()
        version_raw = self.doc_version_entry.get().strip()
        if not document_id:
            raise RuntimeError("document id is required")
        try:
            version = int(version_raw)
        except ValueError as exc:
            raise RuntimeError("version must be integer") from exc
        return document_id, version

    def _split_csv(self, raw: str) -> set[str]:
        return {v.strip() for v in raw.split(",") if v.strip()}

    def _build_sign_request_or_none(self):
        sign_input = self.sign_input_entry.get().strip()
        if not sign_input:
            return None
        current_user = self.controller.current_user()
        if current_user is None:
            raise RuntimeError("login required")
        return SignRequest(
            input_pdf=Path(sign_input),
            output_pdf=Path(self.sign_output_entry.get().strip()) if self.sign_output_entry.get().strip() else None,
            signature_png=Path(self.sign_png_entry.get().strip()) if self.sign_png_entry.get().strip() else None,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
            overwrite_output=False,
            dry_run=True,
            sign_mode="visual",
            signer_user=current_user.username,
            password=self.sign_password_entry.get().strip() or None,
            reason="ui_mvp",
        )

    def _append_output(self, title: str, payload: object) -> None:
        self.output.insert(tk.END, f"{title}\n")
        if hasattr(payload, "__dataclass_fields__"):
            rendered = json.dumps(asdict(payload), indent=2, ensure_ascii=True, default=str) + "\n\n"
        else:
            rendered = json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n\n"
        self.output.insert(tk.END, rendered)
        self.output.see(tk.END)
        if self.output_popout is not None:
            self.output_popout.insert(tk.END, f"{title}\n")
            self.output_popout.insert(tk.END, rendered)
            self.output_popout.see(tk.END)

    def _clear_output(self) -> None:
        self.output.delete("1.0", tk.END)
        if self.output_popout is not None:
            self.output_popout.delete("1.0", tk.END)

    def _toggle_output_window(self) -> None:
        if self.output_window is None:
            self._open_output_window()
        else:
            self._close_output_window()

    def _open_output_window(self) -> None:
        if self.output_window is not None:
            self.output_window.lift()
            return
        window = tk.Toplevel(self)
        window.title("QmTool Output (Topmost)")
        window.geometry("620x380")
        window.attributes("-topmost", True)
        header = ttk.Frame(window)
        header.pack(fill=tk.X)
        ttk.Button(header, text="Close", command=self._close_output_window).pack(side=tk.RIGHT, padx=4, pady=2)
        text = tk.Text(window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", self.output.get("1.0", tk.END))
        text.see(tk.END)
        self.output_window = window
        self.output_popout = text
        self.output_toggle_btn.configure(text="Output Popout (On)")
        window.protocol("WM_DELETE_WINDOW", self._close_output_window)

    def _close_output_window(self) -> None:
        if self.output_window is not None:
            self.output_window.destroy()
        self.output_window = None
        self.output_popout = None
        self.output_toggle_btn.configure(text="Output Popout")

    def _handle(self, fn) -> None:
        try:
            payload = fn()
            if payload is not None:
                self._append_output("OK", payload)
            self._refresh_user_label()
        except (RuntimeError, DocumentWorkflowError, SignatureError, ValueError, KeyError) as exc:
            self._append_output("BLOCKED", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._append_output("FAILED", {"message": str(exc)})

    def _refresh_user_label(self) -> None:
        user = self.controller.current_user()
        if user is None:
            self.user_label.configure(text="Current user: -")
        else:
            self.user_label.configure(text=f"Current user: {user.username} ({user.role})")

    def _on_login(self) -> None:
        self._handle(lambda: self.controller.login(self.username_entry.get(), self.password_entry.get()))

    def _on_logout(self) -> None:
        self._handle(lambda: self.controller.logout() or {"status": "logged_out"})

    def _on_create_version(self) -> None:
        self._handle(lambda: self.controller.create_document_version(*self._doc_ref()))

    def _on_assign_roles(self) -> None:
        def _run():
            doc_id, version = self._doc_ref()
            return self.controller.assign_roles(
                doc_id,
                version,
                editors=self._split_csv(self.editors_entry.get()),
                reviewers=self._split_csv(self.reviewers_entry.get()),
                approvers=self._split_csv(self.approvers_entry.get()),
            )

        self._handle(_run)

    def _on_start_workflow(self) -> None:
        self._handle(lambda: self.controller.start_workflow(*self._doc_ref(), profile_id=self.profile_entry.get().strip()))

    def _on_complete_editing(self) -> None:
        self._handle(lambda: self.controller.complete_editing(*self._doc_ref(), sign_request=self._build_sign_request_or_none()))

    def _on_review_accept(self) -> None:
        self._handle(lambda: self.controller.review_accept(*self._doc_ref()))

    def _on_approval_accept(self) -> None:
        self._handle(lambda: self.controller.approval_accept(*self._doc_ref(), sign_request=self._build_sign_request_or_none()))

    def _on_abort_workflow(self) -> None:
        self._handle(lambda: self.controller.abort_workflow(*self._doc_ref()))

    def _on_archive(self) -> None:
        self._handle(lambda: self.controller.archive(*self._doc_ref()))

    def _on_load_details(self) -> None:
        self._handle(lambda: self.controller.get_document(*self._doc_ref()))

    def _on_pool_list(self) -> None:
        self._handle(lambda: self.controller.list_pool(DocumentStatus.PLANNED))

    def _on_settings_list_modules(self) -> None:
        self._handle(lambda: self.controller.list_settings_modules())

    def _on_settings_get(self) -> None:
        self._handle(lambda: self.controller.get_settings(self.settings_module_entry.get().strip()))

    def _on_settings_set(self) -> None:
        def _run():
            module_id = self.settings_module_entry.get().strip()
            values = json.loads(self.settings_json.get("1.0", tk.END).strip())
            return self.controller.set_settings(module_id, values)

        self._handle(_run)

    def _on_create_user(self) -> None:
        self._handle(
            lambda: self.controller.create_user(
                self.new_user_entry.get().strip(),
                self.new_password_entry.get().strip(),
                self.new_role.get().strip(),
            )
        )

    def _on_list_users(self) -> None:
        self._handle(lambda: self.controller.list_users())


def run_smoke_test() -> int:
    controller = UiController()
    controller.logout()
    doc_id = f"DOC-UI-EXE-SMOKE-{uuid.uuid4().hex[:8]}"
    smoke_password = os.environ.get("QMTOOL_ADMIN_PASSWORD", "admin")
    controller.login("admin", smoke_password)
    controller.create_document_version(doc_id, 1)
    controller.assign_roles(doc_id, 1, editors={"admin"}, reviewers={"user"}, approvers={"qmb"})
    controller.start_workflow(doc_id, 1, profile_id="long_release")
    rows = controller.list_pool(DocumentStatus.PLANNED)
    print(json.dumps({"smoke": "ok", "document_id": doc_id, "pool_planned_count": len(rows)}, ensure_ascii=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QmTool UI MVP")
    parser.add_argument("--smoke-test", action="store_true", help="Run non-interactive smoke test and exit")
    args = parser.parse_args(argv)
    if args.smoke_test:
        return run_smoke_test()
    controller = UiController()
    app = QmToolGui(controller)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

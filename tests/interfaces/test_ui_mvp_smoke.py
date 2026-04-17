from __future__ import annotations

import tempfile
import unittest
import uuid

import importlib.util
from pathlib import Path
import subprocess
import sys
import tkinter as tk

from PIL import Image

from interfaces.gui.main import QmToolGui, UiController
from modules.documents.contracts import DocumentStatus
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput


def _write_test_pdf(path: Path) -> None:
    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as fh:
            writer.write(fh)
        return
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
        b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
    )


def _write_test_png(path: Path) -> None:
    img = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
    for x in range(10, 110):
        img.putpixel((x, 20), (0, 0, 0, 255))
    img.save(path, format="PNG")


def _build_sign_request(input_pdf: Path, output_pdf: Path, signature_png: Path, signer_user: str, password: str) -> SignRequest:
    return SignRequest(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        signature_png=signature_png,
        placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
        layout=LabelLayoutInput(show_signature=True, show_name=True, show_date=True),
        overwrite_output=True,
        dry_run=False,
        sign_mode="visual",
        signer_user=signer_user,
        password=password,
        reason="ui_smoke",
    )


class UiMvpSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = UiController()
        self.controller.logout()

    def tearDown(self) -> None:
        self.controller.logout()

    def test_multi_account_workflow_smoke(self) -> None:
        doc_id = f"DOC-UI-SMOKE-{uuid.uuid4().hex[:8]}"
        self.controller.login("admin", "admin")
        self.controller.create_document_version(doc_id, 1)
        self.controller.assign_roles(doc_id, 1, editors={"admin"}, reviewers={"user"}, approvers={"qmb"})
        self.controller.start_workflow(doc_id, 1, profile_id="long_release")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            output_pdf = root / "output.pdf"
            signature_png = root / "sig.png"
            _write_test_pdf(input_pdf)
            _write_test_png(signature_png)

            edit_request = _build_sign_request(input_pdf, output_pdf, signature_png, signer_user="admin", password="admin")
            state = self.controller.complete_editing(doc_id, 1, sign_request=edit_request)
            self.assertEqual(state.status, DocumentStatus.IN_REVIEW)

            self.controller.login("user", "user")
            review_request = _build_sign_request(input_pdf, output_pdf, signature_png, signer_user="user", password="user")
            state = self.controller.review_accept(doc_id, 1, sign_request=review_request)
            self.assertEqual(state.status, DocumentStatus.IN_APPROVAL)

            self.controller.login("qmb", "qmb")
            approve_request = _build_sign_request(input_pdf, output_pdf, signature_png, signer_user="qmb", password="qmb")
            state = self.controller.approval_accept(doc_id, 1, sign_request=approve_request)
            self.assertEqual(state.status, DocumentStatus.APPROVED)
            state = self.controller.archive(doc_id, 1)
            self.assertEqual(state.status, DocumentStatus.ARCHIVED)

    def test_central_error_path_for_non_privileged_settings_write(self) -> None:
        self.controller.login("user", "user")
        with self.assertRaises(RuntimeError):
            self.controller.set_settings("signature", {"require_password": False, "default_mode": "visual"})

    def test_governance_critical_settings_require_ack_in_gui(self) -> None:
        self.controller.login("admin", "admin")
        with self.assertRaises(ValueError):
            self.controller.set_settings("signature", {"require_password": False, "default_mode": "visual"})
        updated = self.controller.set_settings(
            "signature",
            {
                "require_password": False,
                "default_mode": "visual",
                "_acknowledge_governance_change": True,
            },
        )
        self.assertEqual(updated.get("require_password"), False)

    def test_ui_entry_smoke_flag_runs_headless(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "interfaces.gui.main", "--smoke-test"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn('"smoke": "ok"', result.stdout)

    def test_output_dual_mode_mirrors_to_popout(self) -> None:
        try:
            app = QmToolGui(self.controller)
        except tk.TclError:
            self.skipTest("Tk is not available in this environment")
            return
        app.withdraw()
        try:
            app._append_output("OK", {"message": "bottom-only"})
            bottom_text = app.output.get("1.0", tk.END)
            self.assertIn('"message": "bottom-only"', bottom_text)

            app._open_output_window()
            app._append_output("OK", {"message": "mirrored"})
            self.assertIsNotNone(app.output_popout)
            assert app.output_popout is not None
            popout_text = app.output_popout.get("1.0", tk.END)
            self.assertIn('"message": "mirrored"', popout_text)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()

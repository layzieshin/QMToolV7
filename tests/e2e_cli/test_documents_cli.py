from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

from PIL import Image


def run_cli(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
    )


class DocumentsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        run_cli("logout")

    def tearDown(self) -> None:
        run_cli("logout")

    @staticmethod
    def _login(username: str, password: str) -> None:
        result = run_cli("login", "--username", username, "--password", password)
        assert result.returncode == 0, result.stderr + result.stdout

    @staticmethod
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

    @staticmethod
    def _write_test_png(path: Path) -> None:
        img = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
        for x in range(10, 110):
            img.putpixel((x, 20), (0, 0, 0, 255))
        img.save(path, format="PNG")

    @staticmethod
    def _write_test_docx(path: Path) -> None:
        path.write_bytes(b"docx-binary-content")

    @staticmethod
    def _write_test_dotx(path: Path) -> None:
        path.write_bytes(b"dotx-binary-content")

    @staticmethod
    def _review_accept_signed(doc_id: str, signer_password: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            DocumentsCliTest._write_test_pdf(input_pdf)
            DocumentsCliTest._write_test_png(signature_png)
            return run_cli(
                "documents",
                "review-accept",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                signer_password,
                "--sign-dry-run",
            )

    def test_pool_list_by_status_defaults_to_planned(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-PLANNED"
        result = run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)

        listed = run_cli("documents", "pool-list-by-status")
        self.assertEqual(listed.returncode, 0, msg=listed.stderr + listed.stdout)
        payload = json.loads(listed.stdout.strip() or "[]")
        self.assertTrue(any(row["document_id"] == doc_id and row["status"] == "PLANNED" for row in payload))

    def test_workflow_moves_to_approved_with_required_sign_steps(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-APPROVED"
        run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "editor-1",
            "--reviewers",
            "user",
            "--approvers",
            "qmb",
        )
        run_cli("documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "long_release")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            self._write_test_pdf(input_pdf)
            self._write_test_png(signature_png)

            edit_result = run_cli(
                "documents",
                "editing-complete",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                "admin",
                "--sign-dry-run",
            )
            self.assertEqual(edit_result.returncode, 0, msg=edit_result.stderr + edit_result.stdout)

            self._login("user", "user")
            review_result = self._review_accept_signed(doc_id, "user")
            self.assertEqual(review_result.returncode, 0, msg=review_result.stderr + review_result.stdout)

            self._login("qmb", "qmb")
            approval_result = run_cli(
                "documents",
                "approval-accept",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                "qmb",
                "--sign-dry-run",
            )
            self.assertEqual(approval_result.returncode, 0, msg=approval_result.stderr + approval_result.stdout)
            self.assertIn('"status": "APPROVED"', approval_result.stdout)

    def test_intake_commands_register_artifacts(self) -> None:
        self._login("admin", "admin")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "existing.pdf"
            docx_path = root / "existing.docx"
            dotx_path = root / "template.dotx"
            self._write_test_pdf(pdf_path)
            self._write_test_docx(docx_path)
            self._write_test_dotx(dotx_path)

            run_cli("documents", "import-pdf", "--document-id", "DOC-PDF", "--version", "1", "--input", str(pdf_path))
            run_cli("documents", "import-docx", "--document-id", "DOC-DOCX", "--version", "1", "--input", str(docx_path))
            run_cli(
                "documents",
                "create-from-template",
                "--document-id",
                "DOC-TPL",
                "--version",
                "1",
                "--template",
                str(dotx_path),
            )

            artifacts_pdf = run_cli("documents", "pool-list-artifacts", "--document-id", "DOC-PDF", "--version", "1")
            self.assertEqual(artifacts_pdf.returncode, 0, msg=artifacts_pdf.stderr + artifacts_pdf.stdout)
            payload_pdf = json.loads(artifacts_pdf.stdout.strip() or "[]")
            self.assertTrue(any(item["artifact_type"] == "SOURCE_PDF" for item in payload_pdf))

            artifacts_docx = run_cli("documents", "pool-list-artifacts", "--document-id", "DOC-DOCX", "--version", "1")
            self.assertEqual(artifacts_docx.returncode, 0, msg=artifacts_docx.stderr + artifacts_docx.stdout)
            payload_docx = json.loads(artifacts_docx.stdout.strip() or "[]")
            self.assertTrue(any(item["artifact_type"] == "SOURCE_DOCX" for item in payload_docx))

            artifacts_tpl = run_cli("documents", "pool-list-artifacts", "--document-id", "DOC-TPL", "--version", "1")
            self.assertEqual(artifacts_tpl.returncode, 0, msg=artifacts_tpl.stderr + artifacts_tpl.stdout)
            payload_tpl = json.loads(artifacts_tpl.stdout.strip() or "[]")
            self.assertTrue(any(item["source_type"] == "TEMPLATE_DOTX" for item in payload_tpl))

    def test_documents_commands_require_login(self) -> None:
        run_cli("logout")
        result = run_cli("documents", "pool-list-by-status")
        self.assertEqual(result.returncode, 6)
        self.assertIn("login required", result.stdout.lower())

    def test_non_participant_role_is_blocked_in_review(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-BLOCK"
        run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "admin",
            "--reviewers",
            "user",
            "--approvers",
            "qmb",
        )
        run_cli("documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "long_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            self._write_test_pdf(input_pdf)
            self._write_test_png(signature_png)
            run_cli(
                "documents",
                "editing-complete",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                "admin",
                "--sign-dry-run",
            )

        self._login("qmb", "qmb")
        blocked = self._review_accept_signed(doc_id, "qmb")
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("not assigned as reviewer", blocked.stdout)

    def test_registry_entry_exposes_active_version(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-REGISTRY"
        run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "admin",
            "--reviewers",
            "user",
            "--approvers",
            "qmb",
        )
        run_cli("documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "long_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            self._write_test_pdf(input_pdf)
            self._write_test_png(signature_png)
            done = run_cli(
                "documents",
                "editing-complete",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                "admin",
                "--sign-dry-run",
            )
            self.assertEqual(done.returncode, 0, msg=done.stderr + done.stdout)

        self._login("user", "user")
        self.assertEqual(self._review_accept_signed(doc_id, "user").returncode, 0)
        self._login("qmb", "qmb")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            self._write_test_pdf(input_pdf)
            self._write_test_png(signature_png)
            self.assertEqual(
                run_cli(
                    "documents",
                    "approval-accept",
                    "--document-id",
                    doc_id,
                    "--version",
                    "1",
                    "--sign-input",
                    str(input_pdf),
                    "--sign-output",
                    str(output_pdf),
                    "--sign-signature-png",
                    str(signature_png),
                    "--sign-page",
                    "0",
                    "--sign-x",
                    "100",
                    "--sign-y",
                    "100",
                    "--sign-width",
                    "120",
                    "--signer-password",
                    "qmb",
                    "--sign-dry-run",
                ).returncode,
                0,
            )

        register = run_cli("documents", "pool-get-register", "--document-id", doc_id)
        self.assertEqual(register.returncode, 0, msg=register.stderr + register.stdout)
        payload = json.loads(register.stdout.strip() or "{}")
        self.assertEqual(payload.get("active_version"), 1)
        self.assertEqual(payload.get("register_state"), "VALID")

    def test_owner_cannot_reassign_roles_after_first_signature(self) -> None:
        self._login("user", "user")
        doc_id = "DOC-E2E-OWNER-LOCK"
        run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "user",
            "--reviewers",
            "qmb",
            "--approvers",
            "admin",
        )
        run_cli("documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "long_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            self._write_test_pdf(input_pdf)
            self._write_test_png(signature_png)
            done = run_cli(
                "documents",
                "editing-complete",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--sign-input",
                str(input_pdf),
                "--sign-output",
                str(output_pdf),
                "--sign-signature-png",
                str(signature_png),
                "--sign-page",
                "0",
                "--sign-x",
                "100",
                "--sign-y",
                "100",
                "--sign-width",
                "120",
                "--signer-password",
                "user",
                "--sign-dry-run",
            )
            self.assertEqual(done.returncode, 0, msg=done.stderr + done.stdout)

        blocked = run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "user,admin",
            "--reviewers",
            "qmb",
            "--approvers",
            "admin",
        )
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("owner cannot update roles after first edit signature", blocked.stdout)

    def test_metadata_and_header_commands(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-META"
        created = run_cli(
            "documents",
            "create-version",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--doc-type",
            "VA",
            "--control-class",
            "CONTROLLED",
            "--workflow-profile-id",
            "long_release",
            "--title",
            "Titel A",
            "--description",
            "Beschreibung A",
        )
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)

        header = run_cli("documents", "header-get", "--document-id", doc_id)
        self.assertEqual(header.returncode, 0, msg=header.stderr + header.stdout)
        header_payload = json.loads(header.stdout.strip() or "{}")
        self.assertEqual(header_payload.get("doc_type"), "VA")
        self.assertEqual(header_payload.get("control_class"), "CONTROLLED")

        meta_set = run_cli(
            "documents",
            "metadata-set",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--title",
            "Titel B",
            "--description",
            "Beschreibung B",
            "--custom-fields-json",
            "{\"topic\":\"sterility\"}",
        )
        self.assertEqual(meta_set.returncode, 0, msg=meta_set.stderr + meta_set.stdout)

        meta_get = run_cli("documents", "metadata-get", "--document-id", doc_id, "--version", "1")
        self.assertEqual(meta_get.returncode, 0, msg=meta_get.stderr + meta_get.stdout)
        meta_payload = json.loads(meta_get.stdout.strip() or "{}")
        self.assertEqual(meta_payload.get("title"), "Titel B")
        self.assertEqual(meta_payload.get("doc_type"), "VA")
        self.assertEqual(meta_payload.get("control_class"), "CONTROLLED")
        self.assertEqual(meta_payload.get("custom_fields", {}).get("topic"), "sterility")

        self._login("user", "user")
        blocked_header = run_cli(
            "documents",
            "header-set",
            "--document-id",
            doc_id,
            "--department",
            "QC",
        )
        self.assertEqual(blocked_header.returncode, 6)
        self.assertIn("only qmb or admin", blocked_header.stdout.lower())

        self._login("admin", "admin")
        blocked_custom = run_cli(
            "documents",
            "metadata-set",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--custom-fields-json",
            "{\"status\":\"APPROVED\"}",
        )
        self.assertEqual(blocked_custom.returncode, 6)
        self.assertIn("custom fields must not override steering fields", blocked_custom.stdout.lower())

    def test_workflow_start_blocks_profile_control_class_mismatch(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-MISMATCH"
        created = run_cli(
            "documents",
            "create-version",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--doc-type",
            "VA",
            "--control-class",
            "CONTROLLED",
            "--workflow-profile-id",
            "long_release",
        )
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
        run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "admin",
            "--reviewers",
            "user",
            "--approvers",
            "qmb",
        )
        blocked = run_cli(
            "documents",
            "workflow-start",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--profile-id",
            "external_control",
        )
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("does not match document control_class", blocked.stdout)

    def test_header_set_blocks_doc_type_and_control_class_mutation(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-HEADER-IMMUTABLE"
        created = run_cli(
            "documents",
            "create-version",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--doc-type",
            "VA",
            "--control-class",
            "CONTROLLED",
            "--workflow-profile-id",
            "long_release",
        )
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)

        blocked_doc_type = run_cli(
            "documents",
            "header-set",
            "--document-id",
            doc_id,
            "--doc-type",
            "FB",
        )
        self.assertEqual(blocked_doc_type.returncode, 6)
        self.assertIn("doc_type cannot be changed", blocked_doc_type.stdout.lower())

        blocked_class = run_cli(
            "documents",
            "header-set",
            "--document-id",
            doc_id,
            "--control-class",
            "RECORD",
        )
        self.assertEqual(blocked_class.returncode, 6)
        self.assertIn("control_class cannot be changed", blocked_class.stdout.lower())

    def test_header_set_blocks_workflow_profile_control_class_mismatch(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-HEADER-PROFILE-MISMATCH"
        created = run_cli(
            "documents",
            "create-version",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--doc-type",
            "VA",
            "--control-class",
            "CONTROLLED",
            "--workflow-profile-id",
            "long_release",
        )
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
        blocked = run_cli(
            "documents",
            "header-set",
            "--document-id",
            doc_id,
            "--workflow-profile-id",
            "external_control",
        )
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("does not match document control_class", blocked.stdout)

    def test_metadata_set_blocks_validity_update_before_approval(self) -> None:
        self._login("admin", "admin")
        doc_id = "DOC-E2E-META-DATES"
        created = run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
        blocked = run_cli(
            "documents",
            "metadata-set",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--valid-until",
            "2030-01-01T00:00:00",
        )
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("validity dates can only be updated", blocked.stdout.lower())


if __name__ == "__main__":
    unittest.main()


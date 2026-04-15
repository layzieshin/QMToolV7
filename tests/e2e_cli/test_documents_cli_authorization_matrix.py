from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import uuid
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


class DocumentsCliAuthorizationMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self._run_id = uuid.uuid4().hex[:8]
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
    def _create_and_assign(doc_id: str, creator: str, creator_pw: str, editors: str, reviewers: str, approvers: str) -> None:
        DocumentsCliAuthorizationMatrixTest._login(creator, creator_pw)
        create = run_cli("documents", "create-version", "--document-id", doc_id, "--version", "1")
        assert create.returncode == 0, create.stderr + create.stdout
        assign = run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            editors,
            "--reviewers",
            reviewers,
            "--approvers",
            approvers,
        )
        assert assign.returncode == 0, assign.stderr + assign.stdout

    @staticmethod
    def _start_workflow(doc_id: str) -> subprocess.CompletedProcess[str]:
        return run_cli("documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "long_release")

    @staticmethod
    def _complete_editing_signed(doc_id: str, signer_password: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_pdf = root / "input.pdf"
            signature_png = root / "sig.png"
            output_pdf = root / "output.pdf"
            DocumentsCliAuthorizationMatrixTest._write_test_pdf(input_pdf)
            DocumentsCliAuthorizationMatrixTest._write_test_png(signature_png)
            return run_cli(
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
                signer_password,
                "--sign-dry-run",
            )

    def test_workflow_start_matrix(self) -> None:
        cases = (
            ("owner-user-allowed", "user", "user", "user", "owner path"),
            ("non-owner-user-blocked", "admin", "admin", "user", "blocked"),
            ("qmb-allowed", "admin", "admin", "qmb", "privileged path"),
            ("admin-allowed", "user", "user", "admin", "privileged path"),
        )

        for suffix, creator, creator_pw, actor, _ in cases:
            with self.subTest(case=suffix, actor=actor):
                doc_id = f"DOC-CLI-START-{suffix}"
                doc_id = f"{doc_id}-{self._run_id}"
                self._create_and_assign(doc_id, creator, creator_pw, editors="admin", reviewers="qmb", approvers="admin")
                self._login(actor, actor)
                result = self._start_workflow(doc_id)
                if suffix == "non-owner-user-blocked":
                    self.assertEqual(result.returncode, 6, msg=result.stderr + result.stdout)
                    self.assertIn("only owner, QMB, or ADMIN", result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
                    self.assertIn('"status": "IN_PROGRESS"', result.stdout)

    def test_editing_complete_matrix(self) -> None:
        # owner USER allowed even if not assigned editor
        doc_id_owner = f"DOC-CLI-EDIT-owner-{self._run_id}"
        self._create_and_assign(doc_id_owner, "user", "user", editors="admin", reviewers="qmb", approvers="admin")
        self._login("user", "user")
        self.assertEqual(self._start_workflow(doc_id_owner).returncode, 0)
        owner_result = self._complete_editing_signed(doc_id_owner, "user")
        self.assertEqual(owner_result.returncode, 0, msg=owner_result.stderr + owner_result.stdout)
        self.assertIn('"status": "IN_REVIEW"', owner_result.stdout)

        # non participant USER blocked
        doc_id_blocked = f"DOC-CLI-EDIT-blocked-{self._run_id}"
        self._create_and_assign(doc_id_blocked, "admin", "admin", editors="admin", reviewers="qmb", approvers="admin")
        self._login("admin", "admin")
        self.assertEqual(self._start_workflow(doc_id_blocked).returncode, 0)
        self._login("user", "user")
        blocked = self._complete_editing_signed(doc_id_blocked, "user")
        self.assertEqual(blocked.returncode, 6, msg=blocked.stderr + blocked.stdout)
        self.assertIn("only assigned editors, owner, QMB, or ADMIN", blocked.stdout)

        # QMB allowed
        doc_id_qmb = f"DOC-CLI-EDIT-qmb-{self._run_id}"
        self._create_and_assign(doc_id_qmb, "admin", "admin", editors="admin", reviewers="qmb", approvers="admin")
        self._login("admin", "admin")
        self.assertEqual(self._start_workflow(doc_id_qmb).returncode, 0)
        self._login("qmb", "qmb")
        qmb_result = self._complete_editing_signed(doc_id_qmb, "qmb")
        self.assertEqual(qmb_result.returncode, 0, msg=qmb_result.stderr + qmb_result.stdout)

        # ADMIN allowed even when not owner and not assigned editor
        doc_id_admin = f"DOC-CLI-EDIT-admin-{self._run_id}"
        self._create_and_assign(doc_id_admin, "user", "user", editors="user", reviewers="qmb", approvers="admin")
        self._login("user", "user")
        self.assertEqual(self._start_workflow(doc_id_admin).returncode, 0)
        self._login("admin", "admin")
        admin_result = self._complete_editing_signed(doc_id_admin, "admin")
        self.assertEqual(admin_result.returncode, 0, msg=admin_result.stderr + admin_result.stdout)

    def test_qmb_phase_lock_matrix_for_assign_roles(self) -> None:
        doc_id = f"DOC-CLI-QMB-LOCKS-{self._run_id}"
        self._create_and_assign(doc_id, "admin", "admin", editors="admin", reviewers="qmb", approvers="admin")
        self._login("admin", "admin")
        self.assertEqual(self._start_workflow(doc_id).returncode, 0)
        self.assertEqual(self._complete_editing_signed(doc_id, "admin").returncode, 0)

        self._login("qmb", "qmb")
        editors_locked = run_cli(
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
        self.assertEqual(editors_locked.returncode, 6)
        self.assertIn("QMB cannot change editor roles", editors_locked.stdout)

        reviewers_open = run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "admin",
            "--reviewers",
            "qmb,user",
            "--approvers",
            "admin",
        )
        self.assertEqual(reviewers_open.returncode, 0, msg=reviewers_open.stderr + reviewers_open.stdout)

        self.assertEqual(run_cli("documents", "review-accept", "--document-id", doc_id, "--version", "1").returncode, 0)
        reviewers_locked = run_cli(
            "documents",
            "assign-roles",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--editors",
            "admin",
            "--reviewers",
            "qmb",
            "--approvers",
            "admin",
        )
        self.assertEqual(reviewers_locked.returncode, 6)
        self.assertIn("QMB cannot change reviewer roles", reviewers_locked.stdout)


if __name__ == "__main__":
    unittest.main()

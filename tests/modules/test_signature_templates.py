from __future__ import annotations

from qm_platform.settings.testing import build_settings_service_for_tests
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from dataclasses import replace

from modules.signature.contracts import LabelLayoutInput, SignResult, SignaturePlacementInput
from modules.usermanagement.contracts import issue_user_context
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from modules.signature.errors import PasswordRequiredError, SignatureTemplateError
from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.signature.secure_store import EncryptedSignatureBlobStore
from modules.signature.service import SignatureServiceV2
from modules.signature.sqlite_repository import SQLiteSignatureRepository
from qm_platform.persistence.database_evolution import DatabaseEvolutionService, DatabaseSpec, MigrationStep
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _service_with_repo(root: Path) -> tuple[SignatureServiceV2, SQLiteSignatureRepository]:
    settings = build_settings_service_for_tests(root)
    settings.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    settings.set_module_settings(
        "signature",
        {"require_password": True, "default_mode": "visual"},
        acknowledge_governance_change=True,
        actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
    )
    db_path = root / "templates.db"
    DatabaseEvolutionService(app_home=root, backup_root=root / ".database-backups").migrate(
        (
            DatabaseSpec(
                database_id="signature",
                path=db_path,
                migrations=(
                    MigrationStep(
                        version=1,
                        name="initial",
                        sql_path=_REPO_ROOT / "modules" / "signature" / "migrations" / "0001_initial.sql",
                    ),
                    MigrationStep(
                        version=2,
                        name="user_signature_template_presets",
                        sql_path=_REPO_ROOT / "modules" / "signature" / "migrations" / "0002_user_signature_template_presets.sql",
                    ),
                ),
            ),
        ),
        reason="test_setup",
    )
    repository = SQLiteSignatureRepository(db_path=db_path)
    secure_store = EncryptedSignatureBlobStore(
        root=root / "assets",
        key_file=root / "key.bin",
    )
    service = SignatureServiceV2(
        settings_service=settings,
        logger=LoggerService(root / "logs.jsonl"),
        audit_logger=AuditLogger(root / "audit.jsonl"),
        password_verifier=lambda u, p: u == "admin" and p == "admin",
        repository=repository,
        secure_store=secure_store,
    )
    return service, repository


def _create_pdf(path: Path) -> None:
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


class SignatureTemplatesTest(unittest.TestCase):
    def test_import_gif_create_template_and_sign_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            input_pdf = root / "in.pdf"
            _create_pdf(input_pdf)

            settings = build_settings_service_for_tests(root)
            settings.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
            settings.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                acknowledge_governance_change=True,
                actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
            )
            service, _repository = _service_with_repo(root)
            asset = service.import_signature_asset("admin", gif_path)
            self.assertEqual(asset.media_type, "image/png")

            template = service.create_user_signature_template(
                owner_user_id="admin",
                name="default",
                placement=SignaturePlacementInput(page_index=0, x=10.0, y=20.0, target_width=60.0),
                layout=LabelLayoutInput(show_signature=True, show_name=True, show_date=False, name_text="Admin"),
                signature_asset_id=asset.asset_id,
            )
            rows = service.list_user_signature_templates("admin")
            self.assertTrue(any(r.template_id == template.template_id for r in rows))

            result = service.sign_with_template(
                template_id=template.template_id,
                input_pdf=input_pdf,
                signer_user="admin",
                password="admin",
                dry_run=True,
            )
            self.assertTrue(result.dry_run)
            self.assertFalse(result.signed)

    def test_global_template_copy_and_active_signature_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            settings = build_settings_service_for_tests(root)
            settings.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
            settings.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                acknowledge_governance_change=True,
                actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
            )
            service, _repository = _service_with_repo(root)
            asset = service.import_signature_asset("admin", gif_path)
            service.set_active_signature_asset("admin", asset.asset_id, password="admin")
            self.assertEqual(service.get_active_signature_asset_id("admin"), asset.asset_id)
            with closing(sqlite3.connect(root / "templates.db")) as conn:
                row = conn.execute(
                    "SELECT updated_at FROM user_active_signatures WHERE owner_user_id = ?",
                    ("admin",),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertIsNotNone(datetime.fromisoformat(str(row[0])).tzinfo)
            asset_2 = service.import_signature_asset("admin", gif_path)
            with self.assertRaises(PasswordRequiredError):
                service.set_active_signature_asset("admin", asset_2.asset_id)
            service.set_active_signature_asset("admin", asset_2.asset_id, password="admin")
            self.assertEqual(service.get_active_signature_asset_id("admin"), asset_2.asset_id)
            global_template = service.create_user_signature_template(
                owner_user_id="admin",
                name="global-default",
                placement=SignaturePlacementInput(page_index=0, x=10.0, y=20.0, target_width=60.0),
                layout=LabelLayoutInput(show_signature=True, show_name=True, show_date=True, name_rel_x=2.0),
                signature_asset_id=asset.asset_id,
                scope="global",
            )
            self.assertEqual(global_template.scope, "global")
            copied = service.copy_global_template_to_user(global_template.template_id, "admin")
            self.assertEqual(copied.scope, "user")
            updated = service.update_signature_template(
                template_id=copied.template_id,
                owner_user_id="admin",
                name="user-template-updated",
            )
            self.assertEqual(updated.name, "user-template-updated")
            export = service.export_active_signature("admin", root / "active.png")
            self.assertTrue(export.exists())
            with self.assertRaises(PasswordRequiredError):
                service.clear_active_signature("admin")
            service.clear_active_signature("admin", password="admin")
            self.assertIsNone(service.get_active_signature_asset_id("admin"))

    def test_filename_hint_cannot_escape_temp_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _repository = _service_with_repo(root)
            service.settings_service.set_module_settings(
                "signature",
                {"require_password": False, "default_mode": "visual"},
                acknowledge_governance_change=True,
                actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
            )
            png = root / "ok.png"
            Image.new("RGBA", (16, 8), (0, 0, 0, 255)).save(png, format="PNG")
            escaped = root / "escaped.png"
            asset = service.import_signature_asset_bytes(
                "admin",
                png.read_bytes(),
                filename_hint=r"..\..\escaped.png",
            )
            self.assertFalse(escaped.exists())
            self.assertTrue(asset.asset_id)

    def test_template_preset_fields_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, repository = _service_with_repo(root)
            layout = LabelLayoutInput(show_signature=False, show_name=True, show_date=True, show_time=True)
            created = service.create_user_signature_template(
                owner_user_id="admin",
                name="preset",
                placement=SignaturePlacementInput(page_index=0, x=1.0, y=2.0, target_width=3.0),
                layout=layout,
                signature_asset_id=None,
                document_type="SOP",
                role_context="approver",
            )
            loaded = repository.get_template(created.template_id)
            assert loaded is not None
            self.assertTrue(loaded.layout.show_time)
            self.assertEqual("SOP", loaded.document_type)
            self.assertEqual("approver", loaded.role_context)
            self.assertIsNone(loaded.last_used_at)

    def test_suggestion_prefers_user_scope_and_last_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, repository = _service_with_repo(root)
            placement = SignaturePlacementInput(page_index=0, x=1.0, y=2.0, target_width=3.0)
            layout = LabelLayoutInput(show_signature=False)
            actor = issue_user_context(
                user_id="admin",
                session_id="sess-1",
                request_id="req-1",
                organization_id=INSTALLATION_ORGANIZATION_ID,
                username="admin",
                global_roles=(),
                is_qmb=False,
                authenticated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            older = service.create_user_signature_template(
                owner_user_id="admin",
                name="older",
                placement=placement,
                layout=layout,
                signature_asset_id=None,
                document_type="SOP",
            )
            service.create_user_signature_template(
                owner_user_id="admin",
                name="newer",
                placement=placement,
                layout=layout,
                signature_asset_id=None,
                document_type="SOP",
            )
            service.create_user_signature_template(
                owner_user_id="admin",
                name="global-newer",
                placement=placement,
                layout=layout,
                signature_asset_id=None,
                scope="global",
                document_type="SOP",
            )
            repository.upsert_template(
                replace(older, last_used_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
            )
            suggested = service.suggest_template_for_actor(actor, document_type="SOP")
            assert suggested is not None
            self.assertEqual(older.template_id, suggested.template_id)

    def test_sign_with_template_updates_last_used_at_on_non_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, repository = _service_with_repo(root)
            input_pdf = root / "in.pdf"
            _create_pdf(input_pdf)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            asset = service.import_signature_asset("admin", gif_path)
            template = service.create_user_signature_template(
                owner_user_id="admin",
                name="sign-me",
                placement=SignaturePlacementInput(page_index=0, x=10.0, y=20.0, target_width=60.0),
                layout=LabelLayoutInput(show_signature=True, show_name=False, show_date=False),
                signature_asset_id=asset.asset_id,
            )
            self.assertIsNone(repository.get_template(template.template_id).last_used_at)
            with patch("modules.signature.template_use_cases._utcnow") as mocked_now:
                moment = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
                mocked_now.return_value = moment
                service.sign_with_template(
                    template_id=template.template_id,
                    input_pdf=input_pdf,
                    signer_user="admin",
                    password="admin",
                    dry_run=True,
                )
            self.assertIsNone(repository.get_template(template.template_id).last_used_at)
            with patch.object(service, "sign_with_fixed_position") as mock_sign:
                moment = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
                mock_sign.return_value = SignResult(
                    output_pdf=input_pdf,
                    signed=True,
                    sha256="abc",
                    dry_run=False,
                    mode="visual",
                )
                with patch("modules.signature.template_use_cases._utcnow") as mocked_now:
                    mocked_now.return_value = moment
                    service.sign_with_template(
                        template_id=template.template_id,
                        input_pdf=input_pdf,
                        signer_user="admin",
                        password="admin",
                        dry_run=False,
                    )
            updated = repository.get_template(template.template_id)
            assert updated is not None
            self.assertEqual(moment, updated.last_used_at)

    def test_sign_with_template_touch_preserves_renamed_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, repository = _service_with_repo(root)
            input_pdf = root / "in.pdf"
            _create_pdf(input_pdf)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            asset = service.import_signature_asset("admin", gif_path)
            template = service.create_user_signature_template(
                owner_user_id="admin",
                name="original-name",
                placement=SignaturePlacementInput(page_index=0, x=10.0, y=20.0, target_width=60.0),
                layout=LabelLayoutInput(show_signature=True, show_name=False, show_date=False),
                signature_asset_id=asset.asset_id,
            )
            service.update_signature_template(
                template_id=template.template_id,
                owner_user_id="admin",
                name="renamed-before-sign",
            )
            with patch.object(service, "sign_with_fixed_position") as mock_sign:
                mock_sign.return_value = SignResult(
                    output_pdf=input_pdf,
                    signed=True,
                    sha256="abc",
                    dry_run=False,
                    mode="visual",
                )
                service.sign_with_template(
                    template_id=template.template_id,
                    input_pdf=input_pdf,
                    signer_user="admin",
                    password="admin",
                    dry_run=False,
                )
            updated = repository.get_template(template.template_id)
            assert updated is not None
            self.assertEqual("renamed-before-sign", updated.name)

    def test_sign_with_template_for_actor_foreign_user_scope_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _repository = _service_with_repo(root)
            placement = SignaturePlacementInput(page_index=0, x=1.0, y=2.0, target_width=3.0)
            layout = LabelLayoutInput(show_signature=False)
            template = service.create_user_signature_template(
                owner_user_id="admin",
                name="admin-only",
                placement=placement,
                layout=layout,
                signature_asset_id=None,
            )
            foreign = issue_user_context(
                user_id="other",
                session_id="sess-2",
                request_id="req-2",
                organization_id=INSTALLATION_ORGANIZATION_ID,
                username="other",
                global_roles=(),
                is_qmb=False,
                authenticated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            with self.assertRaises(SignatureTemplateError) as exc:
                service.sign_with_template_for_actor(
                    foreign,
                    template_id=template.template_id,
                    input_pdf=root / "in.pdf",
                    signer_user="other",
                )
            self.assertIn("ownership mismatch", str(exc.exception))

    def test_sign_with_template_for_actor_unknown_has_field_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, _repository = _service_with_repo(root)
            actor = issue_user_context(
                user_id="admin",
                session_id="sess-3",
                request_id="req-3",
                organization_id=INSTALLATION_ORGANIZATION_ID,
                username="admin",
                global_roles=(),
                is_qmb=False,
                authenticated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            with self.assertRaises(SignatureTemplateError) as exc:
                service.sign_with_template_for_actor(
                    actor,
                    template_id="missing-template",
                    input_pdf=root / "in.pdf",
                    signer_user="admin",
                )
            self.assertIsNotNone(exc.exception.field_errors)
            self.assertEqual(exc.exception.field_errors[0]["field"], "template_id")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput
from modules.signature.errors import PasswordRequiredError
from modules.signature.secure_store import EncryptedSignatureBlobStore
from modules.signature.service import SignatureServiceV2
from modules.signature.sqlite_repository import SQLiteSignatureRepository
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.sdk.module_contract import SettingsContribution
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


def _create_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n")


class SignatureTemplatesTest(unittest.TestCase):
    def test_import_gif_create_template_and_sign_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gif_path = root / "sig.gif"
            Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(gif_path, format="GIF")
            input_pdf = root / "in.pdf"
            _create_pdf(input_pdf)

            settings = SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json"))
            settings.registry.register(
                SettingsContribution(
                    module_id="signature",
                    schema_version=1,
                    schema={"type": "object"},
                    defaults={"require_password": True, "default_mode": "visual"},
                    scope="module_global",
                    migrations=[],
                )
            )
            settings.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                acknowledge_governance_change=True,
            )
            repository = SQLiteSignatureRepository(
                db_path=root / "templates.db",
                schema_path=Path("modules/signature/schema.sql"),
            )
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
            settings = SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json"))
            settings.registry.register(
                SettingsContribution(
                    module_id="signature",
                    schema_version=1,
                    schema={"type": "object"},
                    defaults={"require_password": True, "default_mode": "visual"},
                    scope="module_global",
                    migrations=[],
                )
            )
            settings.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                acknowledge_governance_change=True,
            )
            repository = SQLiteSignatureRepository(
                db_path=root / "templates.db",
                schema_path=Path("modules/signature/schema.sql"),
            )
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


if __name__ == "__main__":
    unittest.main()

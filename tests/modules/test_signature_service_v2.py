from __future__ import annotations

import tempfile
import unittest
import importlib.util
import warnings
from pathlib import Path

from PIL import Image

from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from modules.signature.errors import (
    CryptoSigningNotConfiguredError,
    InvalidPlacementError,
    PasswordRequiredError,
)
from modules.signature.service import SignatureServiceV2
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.sdk.module_contract import SettingsContribution
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


def _create_pdf(path: Path) -> None:
    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as fh:
            writer.write(fh)
        return

    # Fallback for environments without pypdf: lightweight, still valid enough for dry-run paths.
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
        b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
    )
    path.write_bytes(pdf_bytes)


def _create_signature_png(path: Path) -> None:
    img = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
    for x in range(10, 110):
        y = 20 + (x % 5)
        img.putpixel((x, y), (0, 0, 0, 255))
    img.save(path, format="PNG")


class SignatureServiceV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # External library warning: known in current pypdf release path, not a product regression.
        warnings.filterwarnings(
            "ignore",
            message=r"Calling `PageObject\.replace_contents\(\)` for pages not assigned to a writer is deprecated.*",
            category=DeprecationWarning,
        )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.input_pdf = root / "input.pdf"
        self.signature_png = root / "sig.png"
        _create_pdf(self.input_pdf)
        _create_signature_png(self.signature_png)

        self.settings_service = SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json"))
        self.settings_service.registry.register(
            SettingsContribution(
                module_id="signature",
                schema_version=1,
                schema={"type": "object"},
                defaults={"require_password": True, "default_mode": "visual"},
                scope="module_global",
                migrations=[],
            )
        )
        self.settings_service.set_module_settings(
            "signature",
            {"require_password": True, "default_mode": "visual"},
            acknowledge_governance_change=True,
        )
        self.logger = LoggerService(root / "logs.jsonl")
        self.audit = AuditLogger(root / "audit.jsonl")
        self.svc = SignatureServiceV2(
            settings_service=self.settings_service,
            logger=self.logger,
            audit_logger=self.audit,
            password_verifier=lambda u, p: u == "admin" and p == "admin",
            crypto_signer=None,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_visual_sign_success(self) -> None:
        if (
            importlib.util.find_spec("pypdf") is None
            or importlib.util.find_spec("reportlab") is None
            or importlib.util.find_spec("PIL") is None
        ):
            self.skipTest("visual-sign dependencies are not installed in this environment")
        out = Path(self.tmp.name) / "signed.pdf"
        req = SignRequest(
            input_pdf=self.input_pdf,
            output_pdf=out,
            signature_png=self.signature_png,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(name_text="Admin User", date_text="2026-01-01"),
            signer_user="admin",
            password="admin",
        )
        res = self.svc.sign_with_fixed_position(req)
        self.assertTrue(res.signed)
        self.assertTrue(out.exists())
        self.assertTrue(bool(res.sha256))

    def test_password_required(self) -> None:
        req = SignRequest(
            input_pdf=self.input_pdf,
            signature_png=self.signature_png,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(name_text="Admin User", date_text="2026-01-01"),
            signer_user="admin",
            password=None,
        )
        with self.assertRaises(PasswordRequiredError):
            self.svc.sign_with_fixed_position(req)

    def test_invalid_placement(self) -> None:
        if importlib.util.find_spec("pypdf") is None:
            self.skipTest("pypdf is not installed in this environment")
        req = SignRequest(
            input_pdf=self.input_pdf,
            signature_png=self.signature_png,
            placement=SignaturePlacementInput(page_index=0, x=590.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(name_text="Admin User", date_text="2026-01-01"),
            signer_user="admin",
            password="admin",
        )
        with self.assertRaises(InvalidPlacementError):
            self.svc.sign_with_fixed_position(req)

    def test_dry_run_without_pdf_tooling(self) -> None:
        req = SignRequest(
            input_pdf=self.input_pdf,
            signature_png=self.signature_png,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(name_text="Admin User", date_text="2026-01-01"),
            signer_user="admin",
            password="admin",
            dry_run=True,
        )
        res = self.svc.sign_with_fixed_position(req)
        self.assertTrue(res.dry_run)
        self.assertFalse(res.signed)

    def test_crypto_mode_requires_adapter(self) -> None:
        req = SignRequest(
            input_pdf=self.input_pdf,
            signature_png=self.signature_png,
            placement=SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0),
            layout=LabelLayoutInput(name_text="Admin User", date_text="2026-01-01"),
            signer_user="admin",
            password="admin",
            sign_mode="crypto",
        )
        with self.assertRaises(CryptoSigningNotConfiguredError):
            self.svc.sign_with_fixed_position(req)

    def test_resolve_runtime_layout_uses_signer_and_timestamp(self) -> None:
        resolved = self.svc.resolve_runtime_layout(
            LabelLayoutInput(show_name=True, show_date=True, name_text=None, date_text=None),
            signer_user="admin",
        )
        self.assertEqual("admin", resolved.name_text)
        self.assertIsNotNone(resolved.date_text)
        assert resolved.date_text is not None
        self.assertGreaterEqual(len(resolved.date_text), 16)
        self.assertIn(":", resolved.date_text)


if __name__ == "__main__":
    unittest.main()


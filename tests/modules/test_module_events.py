from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path

from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from modules.signature.service import SignatureServiceV2
from modules.usermanagement.service import UserManagementService
from qm_platform.events.event_bus import EventBus
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
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
        b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
    )


class ModuleEventsTest(unittest.TestCase):
    def test_usermanagement_publishes_auth_events(self) -> None:
        bus = EventBus()
        events: list[str] = []
        bus.subscribe("domain.usermanagement.auth.succeeded.v1", lambda e: events.append(e.name))
        bus.subscribe("domain.usermanagement.auth.failed.v1", lambda e: events.append(e.name))

        svc = UserManagementService(event_bus=bus)
        self.assertIsNotNone(svc.authenticate("admin", "admin"))
        self.assertIsNone(svc.authenticate("admin", "wrong"))
        self.assertIn("domain.usermanagement.auth.succeeded.v1", events)
        self.assertIn("domain.usermanagement.auth.failed.v1", events)

    def test_signature_service_publishes_dry_run_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "input.pdf"
            _create_pdf(pdf)

            bus = EventBus()
            events: list[str] = []
            bus.subscribe("domain.signature.sign.requested.v1", lambda e: events.append(e.name))
            bus.subscribe("domain.signature.sign.dry_run.v1", lambda e: events.append(e.name))

            settings = SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json"))
            settings.registry.register(
                SettingsContribution(
                    module_id="signature",
                    schema_version=1,
                    schema={"type": "object"},
                    defaults={"require_password": False, "default_mode": "visual"},
                    scope="module_global",
                    migrations=[],
                )
            )
            settings.set_module_settings(
                "signature",
                {"require_password": False, "default_mode": "visual"},
                acknowledge_governance_change=True,
            )
            svc = SignatureServiceV2(
                settings_service=settings,
                logger=LoggerService(root / "logs.jsonl"),
                audit_logger=AuditLogger(root / "audit.jsonl"),
                password_verifier=lambda _u, _p: True,
                event_bus=bus,
                crypto_signer=None,
            )
            svc.sign_with_fixed_position(
                SignRequest(
                    input_pdf=pdf,
                    placement=SignaturePlacementInput(page_index=0, x=10.0, y=10.0, target_width=50.0),
                    layout=LabelLayoutInput(show_signature=False, show_name=False, show_date=False),
                    signer_user="admin",
                    dry_run=True,
                )
            )
            self.assertIn("domain.signature.sign.requested.v1", events)
            self.assertIn("domain.signature.sign.dry_run.v1", events)


if __name__ == "__main__":
    unittest.main()


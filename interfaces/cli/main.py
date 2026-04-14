from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
from getpass import getpass
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from modules.usermanagement.sqlite_repository import SQLiteUserRepository
from modules.usermanagement.password_crypto import is_password_hash
from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, RejectionReason, SystemRole
from modules.documents.errors import DocumentWorkflowError
from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from modules.signature.errors import SignatureError
from qm_platform.events.event_bus import EventBus
from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_service import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMissingError,
    LicenseService,
)
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.log_query_service import LogQueryService
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.health import build_health_report
from qm_platform.runtime.paths import path_writable, resolve_home_path, resource_root, runtime_home
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


def _prompt_if_missing(value: str | None, prompt: str, default: str | None = None) -> str:
    if value is not None and value.strip():
        return value.strip()
    hint = f" [{default}]" if default else ""
    entered = input(f"{prompt}{hint}: ").strip()
    if not entered and default:
        return default
    if not entered:
        raise ValueError(f"{prompt} is required")
    return entered


def _ensure_dev_license(license_file: Path, keyring: PublicKeyring) -> None:
    app_home = license_file.parent.parent
    key_dir = app_home / "storage/platform/license"
    key_dir.mkdir(parents=True, exist_ok=True)
    private_key_file = key_dir / "dev_ed25519_private.pem"
    public_key_file = key_dir / "dev_ed25519_public.pem"

    if not private_key_file.exists() or not public_key_file.exists():
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_key_file.write_bytes(private_bytes)
        public_key_file.write_bytes(public_bytes)

    public_pem = public_key_file.read_text(encoding="utf-8")
    keyring.add_key("dev-key", public_pem)

    private_key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    desired_modules = set(runtime_bootstrap.core_license_tags())

    if license_file.exists():
        existing = json.loads(license_file.read_text(encoding="utf-8"))
        modules = set(existing.get("enabled_modules", []))
        if desired_modules.issubset(modules):
            return
        existing["enabled_modules"] = sorted(modules | desired_modules)
        message = LicenseVerifier.canonical_payload_bytes(existing)
        existing["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
        license_file.write_text(json.dumps(existing, indent=2, ensure_ascii=True), encoding="utf-8")
        return

    payload = {
        "license_id": "DEV-LICENSE-001",
        "issued_to": "Local Development",
        "customer_id": "DEV",
        "plan": "dev",
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "enabled_modules": sorted(desired_modules),
        "device_binding": {"mode": "optional"},
        "constraints": {},
        "key_id": "dev-key",
    }
    message = LicenseVerifier.canonical_payload_bytes(payload)
    payload["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    license_file.parent.mkdir(parents=True, exist_ok=True)
    license_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def build_container() -> RuntimeContainer:
    container = RuntimeContainer()
    app_home = runtime_home()
    resources = resource_root()
    logger = LoggerService(resolve_home_path(app_home, "storage/platform/logs/platform.log"))
    audit = AuditLogger(resolve_home_path(app_home, "storage/platform/logs/audit.log"))
    events = EventBus()
    settings = SettingsService(SettingsRegistry(), SettingsStore(resolve_home_path(app_home, "storage/platform/settings.json")))

    keyring = PublicKeyring()
    license_file = resolve_home_path(app_home, "license/license.json")
    license_mode = os.environ.get("QMTOOL_LICENSE_MODE", "dev").strip().lower()
    if license_mode in ("dev", "auto"):
        _ensure_dev_license(license_file, keyring)
    else:
        dev_public_key = resolve_home_path(app_home, "storage/platform/license/dev_ed25519_public.pem")
        if dev_public_key.exists():
            keyring.add_key("dev-key", dev_public_key.read_text(encoding="utf-8"))
    license_service = LicenseService(
        license_file=license_file,
        verifier=LicenseVerifier(keyring),
        policy=LicensePolicy(),
    )
    license_guard = LicenseGuard(license_service)

    container.register_port("logger", logger)
    container.register_port("audit_logger", audit)
    container.register_port(
        "log_query_service",
        LogQueryService(
            platform_log_file=resolve_home_path(app_home, "storage/platform/logs/platform.log"),
            audit_log_file=resolve_home_path(app_home, "storage/platform/logs/audit.log"),
        ),
    )
    container.register_port("event_bus", events)
    container.register_port("settings_service", settings)
    container.register_port("license_service", license_service)
    container.register_port("license_guard", license_guard)
    container.register_port("app_home", app_home)
    container.register_port("resource_root", resources)
    return container


def _resolve_runtime_paths(app_home: Path) -> dict[str, str]:
    return {
        "users_db_path": "storage/platform/users.db",
        "documents_db_path": "storage/documents/documents.db",
        "artifacts_root": "storage/documents/artifacts",
        "registry_db_path": "storage/documents/registry.db",
        "logs_dir": "storage/platform/logs",
        "license_file": "license/license.json",
    }


def _seed_admin_direct(app_home: Path, users_db_path: str, username: str, password: str) -> None:
    db_path = resolve_home_path(app_home, users_db_path)
    schema_path = Path("modules/usermanagement/schema.sql")
    repository = SQLiteUserRepository(db_path=db_path, schema_path=schema_path)
    existing = repository.get_by_username(username)
    if existing is None:
        repository.create_user(username, password, "Admin")
        return
    repository.change_password(username, password)


def cmd_init(args: argparse.Namespace) -> int:
    if args.app_home:
        os.environ["QMTOOL_HOME"] = str(Path(args.app_home).resolve())
    app_home = runtime_home()
    defaults = _resolve_runtime_paths(app_home)
    non_interactive = bool(args.non_interactive)
    try:
        users_db_path = args.users_db_path or (
            defaults["users_db_path"] if non_interactive else _prompt_if_missing(None, "users_db_path", defaults["users_db_path"])
        )
        documents_db_path = args.documents_db_path or (
            defaults["documents_db_path"] if non_interactive else _prompt_if_missing(None, "documents_db_path", defaults["documents_db_path"])
        )
        artifacts_root = args.artifacts_root or (
            defaults["artifacts_root"] if non_interactive else _prompt_if_missing(None, "artifacts_root", defaults["artifacts_root"])
        )
        registry_db_path = args.registry_db_path or (
            defaults["registry_db_path"] if non_interactive else _prompt_if_missing(None, "registry_db_path", defaults["registry_db_path"])
        )
        admin_username = args.admin_username or "admin"
        admin_password = args.admin_password
        if not admin_password:
            if non_interactive:
                raise ValueError("--admin-password is required in --non-interactive mode")
            admin_password = getpass("admin_password: ").strip()
        if not admin_password:
            raise ValueError("admin_password is required")

        container = build_container()
        lifecycle = runtime_bootstrap.register_core_modules(container)
        lifecycle.start()
        settings_service: SettingsService = container.get_port("settings_service")
        user_cfg = settings_service.get_module_settings("usermanagement")
        user_cfg["users_db_path"] = users_db_path
        user_cfg["seed_mode"] = "hardened"
        settings_service.set_module_settings("usermanagement", user_cfg, acknowledge_governance_change=True)

        docs_cfg = settings_service.get_module_settings("documents")
        docs_cfg["documents_db_path"] = documents_db_path
        docs_cfg["artifacts_root"] = artifacts_root
        settings_service.set_module_settings("documents", docs_cfg, acknowledge_governance_change=True)

        reg_cfg = settings_service.get_module_settings("registry")
        reg_cfg["registry_db_path"] = registry_db_path
        settings_service.set_module_settings("registry", reg_cfg, acknowledge_governance_change=True)

        _seed_admin_direct(app_home, users_db_path, admin_username, admin_password)
        print(
            json.dumps(
                {
                    "status": "initialized",
                    "app_home": str(app_home),
                    "users_db_path": users_db_path,
                    "documents_db_path": documents_db_path,
                    "artifacts_root": artifacts_root,
                    "registry_db_path": registry_db_path,
                    "admin_username": admin_username,
                    "seed_mode": "hardened",
                },
                ensure_ascii=True,
            )
        )
        return 0
    except (ValueError, KeyError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7


def _all_user_passwords_hashed(users_db: Path) -> bool:
    if not users_db.exists():
        return False
    with sqlite3.connect(users_db) as conn:
        rows = conn.execute("SELECT password FROM users").fetchall()
    if not rows:
        return False
    return all(is_password_hash(str(row[0])) for row in rows if row[0] is not None)


def cmd_doctor(*, strict: bool = False) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    app_home = container.get_port("app_home")
    settings_service: SettingsService = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    user_cfg = settings_service.get_module_settings("usermanagement")
    docs_cfg = settings_service.get_module_settings("documents")
    reg_cfg = settings_service.get_module_settings("registry")
    checks = {}
    paths = {
        "users_db": resolve_home_path(app_home, user_cfg.get("users_db_path", "storage/platform/users.db")),
        "documents_db": resolve_home_path(app_home, docs_cfg.get("documents_db_path", "storage/documents/documents.db")),
        "artifacts_root": resolve_home_path(app_home, docs_cfg.get("artifacts_root", "storage/documents/artifacts")),
        "registry_db": resolve_home_path(app_home, reg_cfg.get("registry_db_path", "storage/documents/registry.db")),
        "settings_file": resolve_home_path(app_home, "storage/platform/settings.json"),
        "license_file": resolve_home_path(app_home, "license/license.json"),
    }
    for key, path in paths.items():
        checks[f"path:{key}:exists_or_parent"] = bool(path.exists() or path.parent.exists())
        checks[f"path:{key}:writable"] = path_writable(path)
    checks["license:readable"] = paths["license_file"].exists()
    checks["settings:modules_registered"] = all(
        module_id in settings_service.registry.list_module_ids()
        for module_id in ("usermanagement", "documents", "registry", "signature", "training")
    )
    checks["users:admin_exists"] = any(u.username == "admin" and u.role == "Admin" for u in usermanagement.list_users())
    if strict:
        checks["security:seed_mode_hardened"] = str(user_cfg.get("seed_mode", "")).strip() == "hardened"
        checks["security:password_hashes_only"] = _all_user_passwords_hashed(paths["users_db"])
    ok = all(checks.values())
    print(
        json.dumps(
            {
                "ok": ok,
                "strict_mode": strict,
                "app_home": str(app_home),
                "checks": checks,
            },
            ensure_ascii=True,
        )
    )
    return 0 if ok else 8


def cmd_health() -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    report = build_health_report(lifecycle)
    logger: LoggerService = container.get_port("logger")
    logger.info("cli", "health check executed", {"ok": report.ok, "modules": report.modules})
    state = "OK" if report.ok else "FAILED"
    print(f"{state}: platform health")
    print(f"Modules: {', '.join(report.modules) if report.modules else '-'}")
    caps = ", ".join(sorted(report.capabilities.keys())) if report.capabilities else "-"
    print(f"Capabilities: {caps}")
    if report.failed_modules:
        print(f"FailedModules: {report.failed_modules}")
    return 0


def cmd_license_check(module: str) -> int:
    container = build_container()
    guard: LicenseGuard = container.get_port("license_guard")
    try:
        guard.ensure_writable_operation_allowed(module)
    except (LicenseMissingError, LicenseInvalidError, LicenseExpiredError, RuntimeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"OK: module '{module}' is licensed")
    return 0


def cmd_login(username: str, password: str) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("usermanagement_service")
    user = service.login(username, password)
    if user is None:
        print("BLOCKED: invalid credentials")
        return 3
    print(f"OK: authenticated as '{user.username}' with role '{user.role}'")
    return 0


def cmd_logout() -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("usermanagement_service")
    service.logout()
    print("OK: logged out")
    return 0


def _resolve_current_user_and_role(usermanagement) -> tuple[object | None, SystemRole | None]:
    current_user = usermanagement.get_current_user()
    if current_user is None:
        return None, None
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    return current_user, role_map.get(current_user.role)


def cmd_sign_visual(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("signature_service")
    date_text = args.date_text or datetime.now().strftime(args.date_format)
    name_text = args.name_text or args.signer_user
    request = SignRequest(
        input_pdf=Path(args.input),
        output_pdf=Path(args.output) if args.output else None,
        signature_png=Path(args.signature_png) if args.signature_png else None,
        placement=SignaturePlacementInput(
            page_index=args.page,
            x=args.x,
            y=args.y,
            target_width=args.width,
        ),
        layout=LabelLayoutInput(
            show_signature=args.show_signature,
            show_name=args.show_name,
            show_date=args.show_date,
            name_text=name_text if args.show_name else None,
            date_text=date_text if args.show_date else None,
            name_position=args.name_pos,
            date_position=args.date_pos,
            name_font_size=args.name_size,
            date_font_size=args.date_size,
            color_hex=args.color,
            name_above=args.name_above,
            name_below=args.name_below,
            date_above=args.date_above,
            date_below=args.date_below,
            x_offset=args.x_offset,
        ),
        overwrite_output=args.overwrite_output,
        dry_run=args.dry_run,
        sign_mode=args.mode,
        signer_user=args.signer_user,
        password=args.password,
        reason=args.reason,
    )
    try:
        result = service.sign_with_fixed_position(request)
    except SignatureError as exc:
        print(f"BLOCKED: {exc}")
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 5
    status = "DRY-RUN" if result.dry_run else "OK"
    print(f"{status}: signed pdf -> {result.output_pdf}")
    if result.sha256:
        print(f"SHA256: {result.sha256}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    api = container.get_port("signature_api")
    try:
        if args.sign_command == "visual":
            return cmd_sign_visual(args)
        if args.sign_command == "import-asset":
            asset = api.import_signature_asset(args.owner_user_id, Path(args.input))
            print(
                json.dumps(
                    {
                        "asset_id": asset.asset_id,
                        "owner_user_id": asset.owner_user_id,
                        "media_type": asset.media_type,
                        "size_bytes": asset.size_bytes,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-create":
            placement = SignaturePlacementInput(page_index=args.page, x=args.x, y=args.y, target_width=args.width)
            layout = LabelLayoutInput(
                show_signature=args.show_signature,
                show_name=args.show_name,
                show_date=args.show_date,
                name_text=args.name_text,
                date_text=args.date_text,
                name_position=args.name_pos,
                date_position=args.date_pos,
                name_font_size=args.name_size,
                date_font_size=args.date_size,
                color_hex=args.color,
                name_above=args.name_above,
                name_below=args.name_below,
                date_above=args.date_above,
                date_below=args.date_below,
                x_offset=args.x_offset,
            )
            template = api.create_user_signature_template(
                owner_user_id=args.owner_user_id,
                name=args.name,
                placement=placement,
                layout=layout,
                signature_asset_id=args.asset_id,
            )
            print(
                json.dumps(
                    {
                        "template_id": template.template_id,
                        "owner_user_id": template.owner_user_id,
                        "name": template.name,
                        "signature_asset_id": template.signature_asset_id,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-list":
            rows = api.list_user_signature_templates(args.owner_user_id)
            print(
                json.dumps(
                    [
                        {
                            "template_id": row.template_id,
                            "owner_user_id": row.owner_user_id,
                            "name": row.name,
                            "signature_asset_id": row.signature_asset_id,
                        }
                        for row in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-sign":
            result = api.sign_with_template(
                template_id=args.template_id,
                input_pdf=Path(args.input),
                signer_user=args.signer_user,
                password=args.password,
                output_pdf=Path(args.output) if args.output else None,
                dry_run=args.dry_run,
                overwrite_output=args.overwrite_output,
                reason=args.reason,
            )
            status = "DRY-RUN" if result.dry_run else "OK"
            print(f"{status}: signed pdf -> {result.output_pdf}")
            if result.sha256:
                print(f"SHA256: {result.sha256}")
            return 0
    except SignatureError as exc:
        print(f"BLOCKED: {exc}")
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 5
    return 1


def _print_documents_state(prefix: str, state) -> None:
    payload = {
        "document_id": state.document_id,
        "version": state.version,
        "status": state.status.value,
        "workflow_active": state.workflow_active,
        "extension_count": state.extension_count,
    }
    print(f"{prefix}: {json.dumps(payload, ensure_ascii=True)}")


def _load_documents_state(service, document_id: str, version: int):
    state = service.get_document_version(document_id, version)
    if state is None:
        raise DocumentWorkflowError(f"document version not found: {document_id} v{version}")
    return state


def _parse_optional_datetime(raw: str | None):
    if raw is None or not raw.strip():
        return None
    return datetime.fromisoformat(raw)


def _build_sign_request(args: argparse.Namespace, reason: str, signer_user: str) -> SignRequest:
    date_text = datetime.now().strftime(args.date_format)
    return SignRequest(
        input_pdf=Path(args.sign_input),
        output_pdf=Path(args.sign_output) if args.sign_output else None,
        signature_png=Path(args.sign_signature_png) if args.sign_signature_png else None,
        placement=SignaturePlacementInput(
            page_index=args.sign_page,
            x=args.sign_x,
            y=args.sign_y,
            target_width=args.sign_width,
        ),
        layout=LabelLayoutInput(
            show_signature=args.sign_show_signature,
            show_name=args.sign_show_name,
            show_date=args.sign_show_date,
            name_text=args.sign_name_text or signer_user,
            date_text=args.sign_date_text or date_text,
            name_position=args.sign_name_pos,
            date_position=args.sign_date_pos,
            name_font_size=args.sign_name_size,
            date_font_size=args.sign_date_size,
            color_hex=args.sign_color,
            name_above=args.sign_name_above,
            name_below=args.sign_name_below,
            date_above=args.sign_date_above,
            date_below=args.sign_date_below,
            x_offset=args.sign_x_offset,
        ),
        overwrite_output=args.sign_overwrite_output,
        dry_run=args.sign_dry_run,
        sign_mode=args.sign_mode,
        signer_user=signer_user,
        password=args.signer_password,
        reason=reason,
    )


def _add_sign_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sign-input")
    parser.add_argument("--sign-output")
    parser.add_argument("--sign-signature-png")
    parser.add_argument("--sign-page", type=int, default=0)
    parser.add_argument("--sign-x", type=float, default=0.0)
    parser.add_argument("--sign-y", type=float, default=0.0)
    parser.add_argument("--sign-width", type=float, default=0.0)
    parser.add_argument("--sign-show-signature", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sign-show-name", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sign-show-date", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sign-name-text")
    parser.add_argument("--sign-date-text")
    parser.add_argument("--date-format", default="%Y-%m-%d")
    parser.add_argument("--sign-name-pos", choices=["above", "below", "off"], default="above")
    parser.add_argument("--sign-date-pos", choices=["above", "below", "off"], default="below")
    parser.add_argument("--sign-name-size", type=int, default=12)
    parser.add_argument("--sign-date-size", type=int, default=12)
    parser.add_argument("--sign-color", default="#000000")
    parser.add_argument("--sign-name-above", type=float, default=6.0)
    parser.add_argument("--sign-name-below", type=float, default=12.0)
    parser.add_argument("--sign-date-above", type=float, default=18.0)
    parser.add_argument("--sign-date-below", type=float, default=24.0)
    parser.add_argument("--sign-x-offset", type=float, default=0.0)
    parser.add_argument("--signer-password")
    parser.add_argument("--sign-mode", choices=["visual", "crypto", "both"], default="visual")
    parser.add_argument("--sign-dry-run", action="store_true")
    parser.add_argument("--sign-overwrite-output", action="store_true")


def cmd_documents(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    pool_api = container.get_port("documents_pool_api")
    workflow_api = container.get_port("documents_workflow_api")
    service = container.get_port("documents_service")
    registry_api = container.get_port("registry_api")
    usermanagement = container.get_port("usermanagement_service")
    current_user, current_role = _resolve_current_user_and_role(usermanagement)
    if current_user is None:
        print("BLOCKED: login required for documents commands")
        return 6
    if current_role is None:
        print(f"BLOCKED: unsupported user role '{current_user.role}'")
        return 6

    try:
        if args.documents_command == "create-version":
            state = workflow_api.create_document_version(
                args.document_id,
                args.version,
                owner_user_id=current_user.user_id,
                title=args.title or args.document_id,
                description=args.description,
                doc_type=DocumentType(args.doc_type),
                control_class=ControlClass(args.control_class),
                workflow_profile_id=args.workflow_profile_id,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "import-pdf":
            state = workflow_api.import_existing_pdf(
                args.document_id,
                args.version,
                Path(args.input),
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "import-docx":
            state = workflow_api.import_existing_docx(
                args.document_id,
                args.version,
                Path(args.input),
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "create-from-template":
            state = workflow_api.create_from_template(
                args.document_id,
                args.version,
                Path(args.template),
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "assign-roles":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.assign_workflow_roles(
                state,
                editors={v.strip() for v in args.editors.split(",") if v.strip()},
                reviewers={v.strip() for v in args.reviewers.split(",") if v.strip()},
                approvers={v.strip() for v in args.approvers.split(",") if v.strip()},
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "workflow-start":
            state = _load_documents_state(service, args.document_id, args.version)
            profile = service.get_profile(args.profile_id)
            state = workflow_api.start_workflow(
                state,
                profile,
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "editing-complete":
            state = _load_documents_state(service, args.document_id, args.version)
            sign_request = (
                _build_sign_request(args, "documents.editing_complete", current_user.username)
                if args.sign_input
                else None
            )
            state = workflow_api.complete_editing(
                state,
                sign_request=sign_request,
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "review-accept":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.accept_review(state, current_user.user_id, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "review-reject":
            state = _load_documents_state(service, args.document_id, args.version)
            reason = RejectionReason(
                template_id=args.reason_template_id,
                template_text=args.reason_template_text,
                free_text=args.reason_free_text,
            )
            state = workflow_api.reject_review(state, current_user.user_id, reason, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "approval-accept":
            state = _load_documents_state(service, args.document_id, args.version)
            sign_request = (
                _build_sign_request(args, "documents.approval_accept", current_user.username)
                if args.sign_input
                else None
            )
            state = workflow_api.accept_approval(
                state,
                current_user.user_id,
                sign_request=sign_request,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "approval-reject":
            state = _load_documents_state(service, args.document_id, args.version)
            reason = RejectionReason(
                template_id=args.reason_template_id,
                template_text=args.reason_template_text,
                free_text=args.reason_free_text,
            )
            state = workflow_api.reject_approval(state, current_user.user_id, reason, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "workflow-abort":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.abort_workflow(
                state,
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "archive":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.archive_approved(state, current_role, actor_user_id=current_user.user_id)
            _print_documents_state("OK", state)
            return 0

        if args.documents_command == "annual-extend":
            state = _load_documents_state(service, args.document_id, args.version)
            state, must_recreate = workflow_api.extend_annual_validity(state, signature_present=args.signature_present)
            _print_documents_state("OK", state)
            print(f"RECREATE_REQUIRED: {str(must_recreate).lower()}")
            return 0

        if args.documents_command == "pool-list-by-status":
            status = DocumentStatus(args.status)
            rows = pool_api.list_by_status(status)
            payload = [{"document_id": row.document_id, "version": row.version, "status": row.status.value} for row in rows]
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "pool-list-artifacts":
            rows = pool_api.list_artifacts(args.document_id, args.version)
            payload = [
                {
                    "artifact_id": row.artifact_id,
                    "artifact_type": row.artifact_type.value,
                    "source_type": row.source_type.value,
                    "storage_key": row.storage_key,
                    "original_filename": row.original_filename,
                    "is_current": row.is_current,
                }
                for row in rows
            ]
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "pool-get-register":
            row = registry_api.get_entry(args.document_id)
            if row is None:
                print("{}")
                return 0
            payload = {
                "document_id": row.document_id,
                "active_version": row.active_version,
                "register_state": row.register_state.value,
                "is_findable": row.is_findable,
                "release_evidence_mode": row.release_evidence_mode.value,
                "last_update_event_id": row.last_update_event_id,
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "header-get":
            row = pool_api.get_header(args.document_id)
            if row is None:
                print("{}")
                return 0
            payload = {
                "document_id": row.document_id,
                "doc_type": row.doc_type.value,
                "control_class": row.control_class.value,
                "workflow_profile_id": row.workflow_profile_id,
                "department": row.department,
                "site": row.site,
                "regulatory_scope": row.regulatory_scope,
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "header-set":
            if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
                print("BLOCKED: only QMB or ADMIN may update document headers")
                return 6
            row = workflow_api.update_document_header(
                args.document_id,
                doc_type=DocumentType(args.doc_type) if args.doc_type else None,
                control_class=ControlClass(args.control_class) if args.control_class else None,
                workflow_profile_id=args.workflow_profile_id,
                department=args.department,
                site=args.site,
                regulatory_scope=args.regulatory_scope,
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            payload = {
                "document_id": row.document_id,
                "doc_type": row.doc_type.value,
                "control_class": row.control_class.value,
                "workflow_profile_id": row.workflow_profile_id,
                "department": row.department,
                "site": row.site,
                "regulatory_scope": row.regulatory_scope,
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "metadata-get":
            state = _load_documents_state(service, args.document_id, args.version)
            payload = {
                "document_id": state.document_id,
                "version": state.version,
                "title": state.title,
                "description": state.description,
                "doc_type": state.doc_type.value,
                "control_class": state.control_class.value,
                "workflow_profile_id": state.workflow_profile_id,
                "valid_from": state.valid_from.isoformat() if state.valid_from else None,
                "valid_until": state.valid_until.isoformat() if state.valid_until else None,
                "next_review_at": state.next_review_at.isoformat() if state.next_review_at else None,
                "custom_fields": state.custom_fields,
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        if args.documents_command == "metadata-set":
            state = _load_documents_state(service, args.document_id, args.version)
            custom_fields = json.loads(args.custom_fields_json) if args.custom_fields_json else None
            if custom_fields is not None and not isinstance(custom_fields, dict):
                print("BLOCKED: --custom-fields-json must be a JSON object")
                return 6
            updated = workflow_api.update_version_metadata(
                state,
                title=args.title,
                description=args.description,
                valid_until=_parse_optional_datetime(args.valid_until),
                next_review_at=_parse_optional_datetime(args.next_review_at),
                custom_fields=custom_fields,
                actor_user_id=current_user.user_id,
                actor_role=current_role,
            )
            _print_documents_state("OK", updated)
            return 0
    except (DocumentWorkflowError, SignatureError, ValueError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7

    return 1


def cmd_users(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    current_user, current_role = _resolve_current_user_and_role(usermanagement)
    if current_user is None or current_role is None:
        print("BLOCKED: login required for users commands")
        return 6
    if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
        print("BLOCKED: only QMB or ADMIN may execute users commands")
        return 6

    try:
        if args.users_command == "list":
            rows = usermanagement.list_users()
            payload = [{"user_id": row.user_id, "username": row.username, "role": row.role} for row in rows]
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.users_command == "create":
            created = usermanagement.create_user(args.username, args.password, args.role)
            print(
                json.dumps(
                    {"user_id": created.user_id, "username": created.username, "role": created.role},
                    ensure_ascii=True,
                )
            )
            return 0
        if args.users_command == "change-password":
            usermanagement.change_password(args.username, args.password)
            print(f"OK: password changed for '{args.username}'")
            return 0
    except (ValueError, KeyError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1


def cmd_settings(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    settings_service: SettingsService = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    current_user, current_role = _resolve_current_user_and_role(usermanagement)
    if current_user is None or current_role is None:
        print("BLOCKED: login required for settings commands")
        return 6

    try:
        if args.settings_command == "list-modules":
            payload = settings_service.registry.list_module_ids()
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.settings_command == "get":
            payload = settings_service.get_module_settings(args.module)
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.settings_command == "set":
            if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
                print("BLOCKED: only QMB or ADMIN may set settings")
                return 6
            values = json.loads(args.values_json)
            if not isinstance(values, dict):
                print("BLOCKED: --values-json must be a JSON object")
                return 6
            settings_service.set_module_settings(
                args.module,
                values,
                acknowledge_governance_change=bool(args.acknowledge_governance_change),
            )
            persisted = settings_service.get_module_settings(args.module)
            print(json.dumps(persisted, ensure_ascii=True))
            return 0
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1


def cmd_training(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    training_api = container.get_port("training_api")
    training_admin_api = container.get_port("training_admin_api")
    current_user, current_role = _resolve_current_user_and_role(usermanagement)
    if current_user is None or current_role is None:
        print("BLOCKED: login required for training commands")
        return 6
    try:
        if args.training_command == "list-required":
            rows = training_api.list_required_for_user(current_user.user_id)
            print(
                json.dumps(
                    [
                        {
                            "assignment_id": r.assignment_id,
                            "document_id": r.document_id,
                            "version": r.version,
                            "status": r.status.value,
                            "active": r.active,
                            "last_score": r.last_score,
                        }
                        for r in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "confirm-read":
            row = training_api.confirm_read(
                user_id=current_user.user_id,
                document_id=args.document_id,
                version=args.version,
                last_page_seen=args.last_page_seen,
                total_pages=args.total_pages,
                scrolled_to_end=args.scrolled_to_end,
            )
            print(
                json.dumps(
                    {
                        "assignment_id": row.assignment_id,
                        "document_id": row.document_id,
                        "version": row.version,
                        "status": row.status.value,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "quiz-start":
            session, questions = training_api.start_quiz(current_user.user_id, args.document_id, args.version)
            print(
                json.dumps(
                    {
                        "session_id": session.session_id,
                        "document_id": session.document_id,
                        "version": session.version,
                        "questions": [
                            {"question_id": q.question_id, "text": q.question_text, "options": list(q.options)}
                            for q in questions
                        ],
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "quiz-answer":
            answers = json.loads(args.answers_json)
            if not isinstance(answers, list):
                print("BLOCKED: --answers-json must be a JSON array")
                return 6
            result = training_api.submit_quiz_answers(args.session_id, [int(v) for v in answers])
            print(
                json.dumps(
                    {
                        "session_id": result.session_id,
                        "score": result.score,
                        "total": result.total,
                        "passed": result.passed,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "comment-add":
            row = training_api.add_comment(current_user.user_id, args.document_id, args.version, args.comment)
            print(json.dumps({"comment_id": row.comment_id}, ensure_ascii=True))
            return 0
        if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
            print("BLOCKED: only QMB or ADMIN may execute training admin commands")
            return 6
        if args.training_command == "admin-list-approved":
            rows = training_admin_api.list_approved_documents()
            print(
                json.dumps(
                    [{"document_id": r.document_id, "version": r.version, "owner_user_id": r.owner_user_id} for r in rows],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "admin-category-create":
            category = training_admin_api.create_category(args.category_id, args.name, description=args.description)
            print(json.dumps({"category_id": category.category_id, "name": category.name}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-category-assign-document":
            training_admin_api.assign_document_to_category(args.category_id, args.document_id)
            print("OK")
            return 0
        if args.training_command == "admin-category-assign-user":
            training_admin_api.assign_user_to_category(args.category_id, args.user_id)
            print("OK")
            return 0
        if args.training_command == "admin-sync":
            count = training_admin_api.sync_required_assignments()
            print(json.dumps({"updated": count}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-quiz-import":
            digest = training_admin_api.import_quiz_questions(
                args.document_id,
                args.version,
                Path(args.input).read_bytes(),
            )
            print(json.dumps({"sha256": digest}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-matrix":
            rows = training_admin_api.list_matrix()
            print(
                json.dumps(
                    [
                        {
                            "user_id": r.user_id,
                            "document_id": r.document_id,
                            "version": r.version,
                            "category_id": r.category_id,
                            "status": r.status.value,
                            "active": r.active,
                        }
                        for r in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
    except (ValueError, KeyError, json.JSONDecodeError, DocumentWorkflowError, SignatureError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="QmToolV4 Platform CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Run platform health check")
    init_parser = sub.add_parser("init", help="Initialize runtime paths and admin seed")
    init_parser.add_argument("--app-home")
    init_parser.add_argument("--users-db-path")
    init_parser.add_argument("--documents-db-path")
    init_parser.add_argument("--artifacts-root")
    init_parser.add_argument("--registry-db-path")
    init_parser.add_argument("--admin-username", default="admin")
    init_parser.add_argument("--admin-password")
    init_parser.add_argument("--non-interactive", action="store_true")
    doctor_parser = sub.add_parser("doctor", help="Check runtime readiness and critical paths")
    doctor_parser.add_argument("--strict", action="store_true", help="Enable strict production security checks")
    license_parser = sub.add_parser("license-check", help="Check module license")
    license_parser.add_argument("--module", required=True)
    login_parser = sub.add_parser("login", help="Authenticate against usermanagement module")
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)
    sub.add_parser("logout", help="Clear active session")
    users_parser = sub.add_parser("users", help="User management operations")
    users_sub = users_parser.add_subparsers(dest="users_command", required=True)
    users_sub.add_parser("list", help="List users")
    user_create = users_sub.add_parser("create", help="Create user")
    user_create.add_argument("--username", required=True)
    user_create.add_argument("--password", required=True)
    user_create.add_argument("--role", choices=["Admin", "QMB", "User"], required=True)
    user_change_password = users_sub.add_parser("change-password", help="Change user password")
    user_change_password.add_argument("--username", required=True)
    user_change_password.add_argument("--password", required=True)
    settings_parser = sub.add_parser("settings", help="Settings operations")
    settings_sub = settings_parser.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("list-modules", help="List modules with settings contribution")
    settings_get = settings_sub.add_parser("get", help="Get module settings")
    settings_get.add_argument("--module", required=True)
    settings_set = settings_sub.add_parser("set", help="Set module settings from JSON object")
    settings_set.add_argument("--module", required=True)
    settings_set.add_argument("--values-json", required=True)
    settings_set.add_argument(
        "--acknowledge-governance-change",
        action="store_true",
        help="Required when changing governance_critical keys",
    )
    sign_parser = sub.add_parser("sign-visual", help="Visual PDF signing with fixed position")
    sign_parser.add_argument("--input", required=True)
    sign_parser.add_argument("--output")
    sign_parser.add_argument("--signature-png")
    sign_parser.add_argument("--page", type=int, default=0)
    sign_parser.add_argument("--x", type=float, required=True)
    sign_parser.add_argument("--y", type=float, required=True)
    sign_parser.add_argument("--width", type=float, required=True)
    sign_parser.add_argument("--show-signature", action=argparse.BooleanOptionalAction, default=True)
    sign_parser.add_argument("--show-name", action=argparse.BooleanOptionalAction, default=True)
    sign_parser.add_argument("--show-date", action=argparse.BooleanOptionalAction, default=True)
    sign_parser.add_argument("--name-text")
    sign_parser.add_argument("--date-text")
    sign_parser.add_argument("--date-format", default="%Y-%m-%d")
    sign_parser.add_argument("--name-pos", choices=["above", "below", "off"], default="above")
    sign_parser.add_argument("--date-pos", choices=["above", "below", "off"], default="below")
    sign_parser.add_argument("--name-size", type=int, default=12)
    sign_parser.add_argument("--date-size", type=int, default=12)
    sign_parser.add_argument("--color", default="#000000")
    sign_parser.add_argument("--name-above", type=float, default=6.0)
    sign_parser.add_argument("--name-below", type=float, default=12.0)
    sign_parser.add_argument("--date-above", type=float, default=18.0)
    sign_parser.add_argument("--date-below", type=float, default=24.0)
    sign_parser.add_argument("--x-offset", type=float, default=0.0)
    sign_parser.add_argument("--signer-user", required=True)
    sign_parser.add_argument("--password")
    sign_parser.add_argument("--reason", default="cli")
    sign_parser.add_argument("--mode", choices=["visual", "crypto", "both"], default="visual")
    sign_parser.add_argument("--dry-run", action="store_true")
    sign_parser.add_argument("--overwrite-output", action="store_true")
    sign_group = sub.add_parser("sign", help="Signature operations")
    sign_sub = sign_group.add_subparsers(dest="sign_command", required=True)
    sign_visual = sign_sub.add_parser("visual", help="Visual PDF signing with fixed position")
    sign_visual.add_argument("--input", required=True)
    sign_visual.add_argument("--output")
    sign_visual.add_argument("--signature-png")
    sign_visual.add_argument("--page", type=int, default=0)
    sign_visual.add_argument("--x", type=float, required=True)
    sign_visual.add_argument("--y", type=float, required=True)
    sign_visual.add_argument("--width", type=float, required=True)
    sign_visual.add_argument("--show-signature", action=argparse.BooleanOptionalAction, default=True)
    sign_visual.add_argument("--show-name", action=argparse.BooleanOptionalAction, default=True)
    sign_visual.add_argument("--show-date", action=argparse.BooleanOptionalAction, default=True)
    sign_visual.add_argument("--name-text")
    sign_visual.add_argument("--date-text")
    sign_visual.add_argument("--date-format", default="%Y-%m-%d")
    sign_visual.add_argument("--name-pos", choices=["above", "below", "off"], default="above")
    sign_visual.add_argument("--date-pos", choices=["above", "below", "off"], default="below")
    sign_visual.add_argument("--name-size", type=int, default=12)
    sign_visual.add_argument("--date-size", type=int, default=12)
    sign_visual.add_argument("--color", default="#000000")
    sign_visual.add_argument("--name-above", type=float, default=6.0)
    sign_visual.add_argument("--name-below", type=float, default=12.0)
    sign_visual.add_argument("--date-above", type=float, default=18.0)
    sign_visual.add_argument("--date-below", type=float, default=24.0)
    sign_visual.add_argument("--x-offset", type=float, default=0.0)
    sign_visual.add_argument("--signer-user", required=True)
    sign_visual.add_argument("--password")
    sign_visual.add_argument("--reason", default="cli")
    sign_visual.add_argument("--mode", choices=["visual", "crypto", "both"], default="visual")
    sign_visual.add_argument("--dry-run", action="store_true")
    sign_visual.add_argument("--overwrite-output", action="store_true")
    sign_import_asset = sign_sub.add_parser("import-asset", help="Import PNG/GIF signature asset securely")
    sign_import_asset.add_argument("--owner-user-id", required=True)
    sign_import_asset.add_argument("--input", required=True)
    sign_template_create = sign_sub.add_parser("template-create", help="Create user signature template")
    sign_template_create.add_argument("--owner-user-id", required=True)
    sign_template_create.add_argument("--name", required=True)
    sign_template_create.add_argument("--asset-id")
    sign_template_create.add_argument("--page", type=int, default=0)
    sign_template_create.add_argument("--x", type=float, required=True)
    sign_template_create.add_argument("--y", type=float, required=True)
    sign_template_create.add_argument("--width", type=float, required=True)
    sign_template_create.add_argument("--show-signature", action=argparse.BooleanOptionalAction, default=True)
    sign_template_create.add_argument("--show-name", action=argparse.BooleanOptionalAction, default=True)
    sign_template_create.add_argument("--show-date", action=argparse.BooleanOptionalAction, default=True)
    sign_template_create.add_argument("--name-text")
    sign_template_create.add_argument("--date-text")
    sign_template_create.add_argument("--name-pos", choices=["above", "below", "off"], default="above")
    sign_template_create.add_argument("--date-pos", choices=["above", "below", "off"], default="below")
    sign_template_create.add_argument("--name-size", type=int, default=12)
    sign_template_create.add_argument("--date-size", type=int, default=12)
    sign_template_create.add_argument("--color", default="#000000")
    sign_template_create.add_argument("--name-above", type=float, default=6.0)
    sign_template_create.add_argument("--name-below", type=float, default=12.0)
    sign_template_create.add_argument("--date-above", type=float, default=18.0)
    sign_template_create.add_argument("--date-below", type=float, default=24.0)
    sign_template_create.add_argument("--x-offset", type=float, default=0.0)
    sign_template_list = sign_sub.add_parser("template-list", help="List user signature templates")
    sign_template_list.add_argument("--owner-user-id", required=True)
    sign_template_sign = sign_sub.add_parser("template-sign", help="Sign using stored template")
    sign_template_sign.add_argument("--template-id", required=True)
    sign_template_sign.add_argument("--input", required=True)
    sign_template_sign.add_argument("--output")
    sign_template_sign.add_argument("--signer-user", required=True)
    sign_template_sign.add_argument("--password")
    sign_template_sign.add_argument("--reason", default="template_cli")
    sign_template_sign.add_argument("--dry-run", action="store_true")
    sign_template_sign.add_argument("--overwrite-output", action="store_true")
    training_parser = sub.add_parser("training", help="Training and document reading operations")
    training_sub = training_parser.add_subparsers(dest="training_command", required=True)
    training_sub.add_parser("list-required", help="List required training assignments for current user")
    tr_confirm = training_sub.add_parser("confirm-read", help="Confirm document was read to last page")
    tr_confirm.add_argument("--document-id", required=True)
    tr_confirm.add_argument("--version", type=int, required=True)
    tr_confirm.add_argument("--last-page-seen", type=int, required=True)
    tr_confirm.add_argument("--total-pages", type=int, required=True)
    tr_confirm.add_argument("--scrolled-to-end", action="store_true")
    tr_quiz_start = training_sub.add_parser("quiz-start", help="Start 3-question random quiz")
    tr_quiz_start.add_argument("--document-id", required=True)
    tr_quiz_start.add_argument("--version", type=int, required=True)
    tr_quiz_answer = training_sub.add_parser("quiz-answer", help="Submit answers for active quiz session")
    tr_quiz_answer.add_argument("--session-id", required=True)
    tr_quiz_answer.add_argument("--answers-json", required=True)
    tr_comment = training_sub.add_parser("comment-add", help="Add feedback comment for document version")
    tr_comment.add_argument("--document-id", required=True)
    tr_comment.add_argument("--version", type=int, required=True)
    tr_comment.add_argument("--comment", required=True)
    training_sub.add_parser("admin-list-approved", help="Admin: list approved documents")
    tr_cat_create = training_sub.add_parser("admin-category-create", help="Admin: create training category")
    tr_cat_create.add_argument("--category-id", required=True)
    tr_cat_create.add_argument("--name", required=True)
    tr_cat_create.add_argument("--description")
    tr_cat_doc = training_sub.add_parser("admin-category-assign-document", help="Admin: map document to category")
    tr_cat_doc.add_argument("--category-id", required=True)
    tr_cat_doc.add_argument("--document-id", required=True)
    tr_cat_user = training_sub.add_parser("admin-category-assign-user", help="Admin: map user to category")
    tr_cat_user.add_argument("--category-id", required=True)
    tr_cat_user.add_argument("--user-id", required=True)
    training_sub.add_parser("admin-sync", help="Admin: sync assignments from categories and approved documents")
    tr_quiz_import = training_sub.add_parser("admin-quiz-import", help="Admin: import quiz JSON for document version")
    tr_quiz_import.add_argument("--document-id", required=True)
    tr_quiz_import.add_argument("--version", type=int, required=True)
    tr_quiz_import.add_argument("--input", required=True)
    training_sub.add_parser("admin-matrix", help="Admin: list training matrix")
    documents_parser = sub.add_parser("documents", help="Document pool and workflow operations")
    documents_sub = documents_parser.add_subparsers(dest="documents_command", required=True)

    doc_create = documents_sub.add_parser("create-version", help="Create a document version in PLANNED")
    doc_create.add_argument("--document-id", required=True)
    doc_create.add_argument("--version", type=int, required=True)
    doc_create.add_argument(
        "--doc-type",
        choices=[v.value for v in DocumentType],
        default=DocumentType.OTHER.value,
    )
    doc_create.add_argument(
        "--control-class",
        choices=[v.value for v in ControlClass],
        default=ControlClass.CONTROLLED.value,
    )
    doc_create.add_argument("--workflow-profile-id", default="long_release")
    doc_create.add_argument("--title")
    doc_create.add_argument("--description")

    doc_import_pdf = documents_sub.add_parser("import-pdf", help="Import existing PDF into document pool")
    doc_import_pdf.add_argument("--document-id", required=True)
    doc_import_pdf.add_argument("--version", type=int, required=True)
    doc_import_pdf.add_argument("--input", required=True)

    doc_import_docx = documents_sub.add_parser("import-docx", help="Import existing DOCX into document pool")
    doc_import_docx.add_argument("--document-id", required=True)
    doc_import_docx.add_argument("--version", type=int, required=True)
    doc_import_docx.add_argument("--input", required=True)

    doc_create_from_template = documents_sub.add_parser(
        "create-from-template",
        help="Create a new document from DOTX (DOCT fallback supported)",
    )
    doc_create_from_template.add_argument("--document-id", required=True)
    doc_create_from_template.add_argument("--version", type=int, required=True)
    doc_create_from_template.add_argument("--template", required=True)

    doc_assign = documents_sub.add_parser("assign-roles", help="Assign editors/reviewers/approvers")
    doc_assign.add_argument("--document-id", required=True)
    doc_assign.add_argument("--version", type=int, required=True)
    doc_assign.add_argument("--editors", required=True, help="Comma-separated user ids")
    doc_assign.add_argument("--reviewers", required=True, help="Comma-separated user ids")
    doc_assign.add_argument("--approvers", required=True, help="Comma-separated user ids")

    doc_start = documents_sub.add_parser("workflow-start", help="Start workflow from PLANNED")
    doc_start.add_argument("--document-id", required=True)
    doc_start.add_argument("--version", type=int, required=True)
    doc_start.add_argument("--profile-id", default="long_release")

    doc_edit_done = documents_sub.add_parser("editing-complete", help="Complete editing and move to next phase")
    doc_edit_done.add_argument("--document-id", required=True)
    doc_edit_done.add_argument("--version", type=int, required=True)
    _add_sign_args(doc_edit_done)

    doc_review_accept = documents_sub.add_parser("review-accept", help="Accept review")
    doc_review_accept.add_argument("--document-id", required=True)
    doc_review_accept.add_argument("--version", type=int, required=True)

    doc_review_reject = documents_sub.add_parser("review-reject", help="Reject review")
    doc_review_reject.add_argument("--document-id", required=True)
    doc_review_reject.add_argument("--version", type=int, required=True)
    doc_review_reject.add_argument("--reason-template-id")
    doc_review_reject.add_argument("--reason-template-text")
    doc_review_reject.add_argument("--reason-free-text")

    doc_approval_accept = documents_sub.add_parser("approval-accept", help="Accept approval")
    doc_approval_accept.add_argument("--document-id", required=True)
    doc_approval_accept.add_argument("--version", type=int, required=True)
    _add_sign_args(doc_approval_accept)

    doc_approval_reject = documents_sub.add_parser("approval-reject", help="Reject approval")
    doc_approval_reject.add_argument("--document-id", required=True)
    doc_approval_reject.add_argument("--version", type=int, required=True)
    doc_approval_reject.add_argument("--reason-template-id")
    doc_approval_reject.add_argument("--reason-template-text")
    doc_approval_reject.add_argument("--reason-free-text")

    doc_abort = documents_sub.add_parser("workflow-abort", help="Abort active workflow and return to PLANNED")
    doc_abort.add_argument("--document-id", required=True)
    doc_abort.add_argument("--version", type=int, required=True)

    doc_archive = documents_sub.add_parser("archive", help="Archive approved document")
    doc_archive.add_argument("--document-id", required=True)
    doc_archive.add_argument("--version", type=int, required=True)

    doc_extend = documents_sub.add_parser("annual-extend", help="Perform annual validity extension")
    doc_extend.add_argument("--document-id", required=True)
    doc_extend.add_argument("--version", type=int, required=True)
    doc_extend.add_argument("--signature-present", action="store_true")

    doc_pool_list = documents_sub.add_parser("pool-list-by-status", help="List documents by status")
    doc_pool_list.add_argument(
        "--status",
        choices=[s.value for s in DocumentStatus],
        default=DocumentStatus.PLANNED.value,
        help="Defaults to PLANNED",
    )

    doc_pool_artifacts = documents_sub.add_parser("pool-list-artifacts", help="List artifacts for a document version")
    doc_pool_artifacts.add_argument("--document-id", required=True)
    doc_pool_artifacts.add_argument("--version", type=int, required=True)

    doc_pool_register = documents_sub.add_parser(
        "pool-get-register",
        help="Get central registry entry for a document",
    )
    doc_pool_register.add_argument("--document-id", required=True)

    doc_header_get = documents_sub.add_parser("header-get", help="Get document header metadata")
    doc_header_get.add_argument("--document-id", required=True)

    doc_header_set = documents_sub.add_parser("header-set", help="Set document header metadata (QMB/Admin)")
    doc_header_set.add_argument("--document-id", required=True)
    doc_header_set.add_argument("--doc-type", choices=[v.value for v in DocumentType])
    doc_header_set.add_argument("--control-class", choices=[v.value for v in ControlClass])
    doc_header_set.add_argument("--workflow-profile-id")
    doc_header_set.add_argument("--department")
    doc_header_set.add_argument("--site")
    doc_header_set.add_argument("--regulatory-scope")

    doc_meta_get = documents_sub.add_parser("metadata-get", help="Get document version metadata")
    doc_meta_get.add_argument("--document-id", required=True)
    doc_meta_get.add_argument("--version", type=int, required=True)

    doc_meta_set = documents_sub.add_parser("metadata-set", help="Set document version metadata")
    doc_meta_set.add_argument("--document-id", required=True)
    doc_meta_set.add_argument("--version", type=int, required=True)
    doc_meta_set.add_argument("--title")
    doc_meta_set.add_argument("--description")
    doc_meta_set.add_argument("--valid-until")
    doc_meta_set.add_argument("--next-review-at")
    doc_meta_set.add_argument("--custom-fields-json")

    args = parser.parse_args()
    if args.command == "health":
        return cmd_health()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "doctor":
        strict_mode = bool(args.strict or os.environ.get("QMTOOL_DOCTOR_STRICT", "0") == "1")
        return cmd_doctor(strict=strict_mode)
    if args.command == "license-check":
        return cmd_license_check(args.module)
    if args.command == "login":
        return cmd_login(args.username, args.password)
    if args.command == "logout":
        return cmd_logout()
    if args.command == "users":
        return cmd_users(args)
    if args.command == "settings":
        return cmd_settings(args)
    if args.command == "sign-visual":
        return cmd_sign_visual(args)
    if args.command == "sign":
        return cmd_sign(args)
    if args.command == "documents":
        return cmd_documents(args)
    if args.command == "training":
        return cmd_training(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


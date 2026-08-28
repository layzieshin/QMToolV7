"""Live PostgreSQL import tests for AP-029 PG01-E signature + cutover rehearsal (collect-only)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from modules.documents import postgres_schema as documents_schema
from modules.documents.contracts import (
    ControlClass,
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
)
from modules.documents.sqlite_pg_import import import_sqlite_to_postgres as import_documents
from modules.documents.api import seed_postgres_workflow_profiles
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from modules.registry import postgres_schema as registry_schema
from modules.registry.contracts import RegisterState, RegistryEntry, ReleaseEvidenceMode
from modules.registry.sqlite_pg_import import import_sqlite_to_postgres as import_registry
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from modules.signature import postgres_schema as signature_schema
from modules.signature.contracts import SignatureAsset
from modules.signature.postgres_repository import PostgresSignatureRepository
from modules.signature.secure_store import EncryptedSignatureBlobStore
from modules.signature.sqlite_pg_import import SqlitePgImportError, fingerprint_sqlite_bundle, import_sqlite_to_postgres
from modules.signature.sqlite_repository import SQLiteSignatureRepository
from modules.usermanagement import postgres_schema as usermanagement_schema
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres
_SIG_MIG = Path(__file__).resolve().parents[3] / "modules" / "signature" / "migrations" / "0001_initial.sql"
_DOC_MIG1 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0001_initial.sql"
_DOC_MIG2 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0002_workflow_profiles.sql"
_REG_MIG = Path(__file__).resolve().parents[3] / "modules" / "registry" / "migrations" / "0001_initial.sql"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _exec_sqlite_script(db_path: Path, script: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def live_signature(live_postgres_env: LivePostgresEnv):
    signature_schema.provision_signature_schema(live_postgres_env.admin_dsn)
    signature_schema.migrate_signature_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS signature CASCADE")


@pytest.fixture
def live_cutover(live_postgres_env: LivePostgresEnv):
    documents_schema.provision_documents_schema(live_postgres_env.admin_dsn)
    documents_schema.migrate_documents_schema(live_postgres_env.migrator_dsn)
    registry_schema.provision_registry_schema(live_postgres_env.admin_dsn)
    registry_schema.migrate_registry_schema(live_postgres_env.migrator_dsn)
    signature_schema.provision_signature_schema(live_postgres_env.admin_dsn)
    signature_schema.migrate_signature_schema(live_postgres_env.migrator_dsn)
    usermanagement_schema.migrate_usermanagement_schema(live_postgres_env.migrator_dsn)
    yield live_postgres_env
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS signature CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS registry CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS documents CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS usermanagement CASCADE")


def test_live_signature_metadata_import(live_signature: LivePostgresEnv, tmp_path: Path) -> None:
    source = tmp_path / "sig.db"
    with sqlite3.connect(source) as conn:
        conn.executescript(_SIG_MIG.read_text(encoding="utf-8"))
    assets = tmp_path / "assets"
    assets.mkdir()
    store = EncryptedSignatureBlobStore(root=assets, key_file=assets / "signature.key")
    plaintext = b"enc-png"
    storage_key = store.put_bytes("u1", ".png", plaintext)
    SQLiteSignatureRepository(source).add_asset(
        SignatureAsset(
            asset_id="a1",
            owner_user_id="u1",
            storage_key=storage_key,
            media_type="image/png",
            original_filename="a1.png",
            sha256=hashlib.sha256(plaintext).hexdigest(),
            size_bytes=len(plaintext),
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
    )
    before = fingerprint_sqlite_bundle(source)
    result = import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=live_signature.runtime_dsn,
        report_dir=tmp_path / "r",
        assets_root=assets,
        blob_reader=store,
    )
    assert result.inserted == 1
    assert fingerprint_sqlite_bundle(source) == before
    loaded = PostgresSignatureRepository(live_signature.runtime_dsn).get_asset("a1")
    assert loaded is not None
    assert loaded.storage_key == storage_key
    assert (assets / storage_key).is_file()


def test_live_signature_storage_negative_missing_reader(
    live_signature: LivePostgresEnv, tmp_path: Path
) -> None:
    source = tmp_path / "sig.db"
    with sqlite3.connect(source) as conn:
        conn.executescript(_SIG_MIG.read_text(encoding="utf-8"))
    assets = tmp_path / "assets"
    assets.mkdir()
    store = EncryptedSignatureBlobStore(root=assets, key_file=assets / "signature.key")
    plaintext = b"x"
    storage_key = store.put_bytes("u1", ".png", plaintext)
    SQLiteSignatureRepository(source).add_asset(
        SignatureAsset(
            asset_id="a1",
            owner_user_id="u1",
            storage_key=storage_key,
            media_type="image/png",
            original_filename="a1.png",
            sha256=hashlib.sha256(plaintext).hexdigest(),
            size_bytes=len(plaintext),
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(SqlitePgImportError, match="blob_reader required"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            postgres_dsn=live_signature.runtime_dsn,
            report_dir=tmp_path / "r",
            assets_root=assets,
        )


_CUTOVER_PROBE = r"""
import json, os, sqlite3, sys
from pathlib import Path

from modules.documents.wiring import register_documents_ports
from modules.registry.wiring import register_registry_ports
from modules.signature.wiring import register_signature_ports
from qm_platform.runtime.backend_bootstrap import wire_backend_usermanagement
from src.backend.bootstrap import build_platform_ports

payload = json.loads(sys.argv[1])
app_home = Path(payload["app_home"])
dsn = payload["dsn"]

# Pin Slot-2 runtime DSN via container ports; never inherit lab QMTOOL_PG_DSN.
os.environ["QMTOOL_HOME"] = str(app_home)
os.environ["QMTOOL_LICENSE_MODE"] = "dev"
os.environ.pop("QMTOOL_PG_DSN", None)
os.environ["QMTOOL_BOOTSTRAP_ADMIN_USERNAME"] = payload["bootstrap_admin_username"]
os.environ["QMTOOL_BOOTSTRAP_ADMIN_PASSWORD"] = payload["bootstrap_admin_password"]

forbidden = {str(Path(p).resolve()) for p in payload["forbidden_sqlite_paths"]}
opens: list[str] = []
_real_connect = sqlite3.connect

def _guarded(database, *args, **kwargs):
    raw = str(database)
    candidate = raw
    if raw.startswith("file:"):
        # URI form used by RO importers; strip query.
        candidate = raw[5:].split("?", 1)[0]
    try:
        resolved = str(Path(candidate).resolve())
    except OSError:
        resolved = candidate
    if resolved in forbidden:
        opens.append(resolved)
        raise RuntimeError(f"productive_sqlite_open_blocked:{resolved}")
    return _real_connect(database, *args, **kwargs)

sqlite3.connect = _guarded  # type: ignore[assignment]

container = build_platform_ports(fail_closed_license=True)
container.register_port("resource_root", Path(payload["resource_root"]))
container.register_port("usermanagement_postgres_dsn", dsn)
container.register_port("documents_postgres_dsn", dsn)
container.register_port("registry_postgres_dsn", dsn)
container.register_port("signature_postgres_dsn", dsn)
container.register_port("documents_runtime_owner", "backend")
container.register_port("signature_runtime_owner", "backend")

wire_backend_usermanagement(container)

# Registry → signature → documents (PG DSNs; real usermanagement_service).
register_registry_ports(container)
register_signature_ports(container)
register_documents_ports(container)

docs = container.get_port("documents_service").get_document_version("DOC-C", 1)
reg = container.get_port("registry_api").get_entry("DOC-C")
sig_api = container.get_port("signature_api")
active_asset_id = sig_api.get_active_signature_asset_id("u1")

print(json.dumps({
    "document_id": None if docs is None else docs.document_id,
    "last_event_id": None if docs is None else docs.last_event_id,
    "registry_document_id": None if reg is None else reg.document_id,
    "active_signature_asset_id": active_asset_id,
    "productive_sqlite_opens": opens,
    "used_postgres_dsn": bool(dsn),
}))
"""


def test_live_cutover_rehearsal_documents_registry_signature(
    live_cutover: LivePostgresEnv, tmp_path: Path
) -> None:
    app_home = tmp_path / "app_home"
    docs = app_home / "storage" / "documents" / "documents.db"
    reg = app_home / "storage" / "registry" / "registry.db"
    sig = app_home / "storage" / "signature" / "templates.db"
    docs.parent.mkdir(parents=True)
    reg.parent.mkdir(parents=True)
    sig.parent.mkdir(parents=True)

    _exec_sqlite_script(docs, _DOC_MIG1.read_text(encoding="utf-8") + _DOC_MIG2.read_text(encoding="utf-8"))
    _exec_sqlite_script(reg, _REG_MIG.read_text(encoding="utf-8"))
    _exec_sqlite_script(sig, _SIG_MIG.read_text(encoding="utf-8"))

    moment = datetime(2024, 6, 1, tzinfo=timezone.utc)
    SQLiteDocumentsRepository(docs).upsert_header(
        DocumentHeader(
            document_id="DOC-C",
            doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
            created_at=moment,
            updated_at=moment,
        )
    )
    SQLiteDocumentsRepository(docs).upsert(
        DocumentVersionState(
            document_id="DOC-C",
            version=1,
            title="Cutover",
            description=None,
            doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="long_release",
            owner_user_id="u1",
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            created_at=moment,
            created_by="u1",
            last_event_id="evt-c",
            last_event_at=moment,
            last_actor_user_id="u1",
        )
    )
    SQLiteRegistryRepository(reg).upsert(
        RegistryEntry(
            document_id="DOC-C",
            active_version=1,
            release_note="c",
            release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
            register_state=RegisterState.VALID,
            is_findable=True,
            valid_from=moment,
            valid_until=None,
            last_update_event_id="evt-c",
            last_update_at=moment,
        )
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    store = EncryptedSignatureBlobStore(root=assets, key_file=assets / "signature.key")
    plaintext = b"cut"
    storage_key = store.put_bytes("u1", ".png", plaintext)
    SQLiteSignatureRepository(sig).add_asset(
        SignatureAsset(
            asset_id="a-c",
            owner_user_id="u1",
            storage_key=storage_key,
            media_type="image/png",
            original_filename="c.png",
            sha256=hashlib.sha256(plaintext).hexdigest(),
            size_bytes=len(plaintext),
            created_at=moment,
        )
    )
    SQLiteSignatureRepository(sig).set_active_signature_asset("u1", "a-c")

    d = import_documents(
        sqlite_path=docs,
        postgres_dsn=live_cutover.runtime_dsn,
        report_dir=tmp_path / "cut/docs",
    )
    r = import_registry(
        sqlite_path=reg,
        postgres_dsn=live_cutover.runtime_dsn,
        report_dir=tmp_path / "cut/reg",
        documents_sqlite_path=docs,
    )
    s = import_sqlite_to_postgres(
        sqlite_path=sig,
        postgres_dsn=live_cutover.runtime_dsn,
        report_dir=tmp_path / "cut/sig",
        assets_root=assets,
        blob_reader=store,
    )
    assert d.status == r.status == s.status == "completed"

    seed_postgres_workflow_profiles(live_cutover.runtime_dsn)

    # Productive SQLite paths become unavailable after cutover (rename to sentinel).
    docs_disabled = docs.with_suffix(".db.cutover-disabled")
    reg_disabled = reg.with_suffix(".db.cutover-disabled")
    sig_disabled = sig.with_suffix(".db.cutover-disabled")
    docs.rename(docs_disabled)
    reg.rename(reg_disabled)
    sig.rename(sig_disabled)
    assert not docs.exists() and not reg.exists() and not sig.exists()

    probe_payload = {
        "app_home": str(app_home),
        "resource_root": str(_REPO_ROOT),
        "dsn": live_cutover.runtime_dsn,
        "forbidden_sqlite_paths": [str(docs), str(reg), str(sig)],
        "bootstrap_admin_username": "cutover-admin",
        "bootstrap_admin_password": "cutover-secret-1",
    }
    proc = subprocess.run(
        [sys.executable, "-c", _CUTOVER_PROBE, json.dumps(probe_payload)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr + "\n" + proc.stdout
    result = json.loads(proc.stdout.strip())
    assert result["document_id"] == "DOC-C"
    assert result["last_event_id"] == "evt-c"
    assert result["registry_document_id"] == "DOC-C"
    assert result["active_signature_asset_id"] == "a-c"
    assert result["productive_sqlite_opens"] == []
    assert result["used_postgres_dsn"] is True

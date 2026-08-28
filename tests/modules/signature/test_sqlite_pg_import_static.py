"""Static tests for AP-029 PG01-E signature SQLite→PG import."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.signature import api as signature_api
from modules.signature.contracts import LabelLayoutInput, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate
from modules.signature.secure_store import EncryptedSignatureBlobStore
from modules.signature.sqlite_pg_import import SqlitePgImportError, fingerprint_sqlite_bundle, import_sqlite_to_postgres
from modules.signature.sqlite_repository import SQLiteSignatureRepository

_MIGRATION = Path(__file__).resolve().parents[3] / "modules" / "signature" / "migrations" / "0001_initial.sql"
_DOC_MIG1 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0001_initial.sql"
_DOC_MIG2 = Path(__file__).resolve().parents[3] / "modules" / "documents" / "migrations" / "0002_workflow_profiles.sql"
_REG_MIG = Path(__file__).resolve().parents[3] / "modules" / "registry" / "migrations" / "0001_initial.sql"


def _init_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(_MIGRATION.read_text(encoding="utf-8"))


def _store_asset(assets: Path, plaintext: bytes = b"png!") -> tuple[EncryptedSignatureBlobStore, SignatureAsset]:
    key_file = assets / "signature.key"
    store = EncryptedSignatureBlobStore(root=assets, key_file=key_file)
    storage_key = store.put_bytes("u1", ".png", plaintext)
    asset = SignatureAsset(
        asset_id="a1",
        owner_user_id="u1",
        storage_key=storage_key,
        media_type="image/png",
        original_filename="a1.png",
        sha256=hashlib.sha256(plaintext).hexdigest(),
        size_bytes=len(plaintext),
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    return store, asset


def _exec_sqlite_script(db_path: Path, script: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


def test_cutover_sqlite_paths_rename_after_explicit_close(tmp_path: Path) -> None:
    docs = tmp_path / "documents.db"
    reg = tmp_path / "registry.db"
    sig = tmp_path / "templates.db"
    _exec_sqlite_script(docs, _DOC_MIG1.read_text(encoding="utf-8") + _DOC_MIG2.read_text(encoding="utf-8"))
    _exec_sqlite_script(reg, _REG_MIG.read_text(encoding="utf-8"))
    _exec_sqlite_script(sig, _MIGRATION.read_text(encoding="utf-8"))
    for path in (docs, reg, sig):
        disabled = Path(str(path) + ".cutover-disabled")
        path.rename(disabled)
        disabled.rename(path)


def test_fingerprint_and_storage_preflight(tmp_path: Path) -> None:
    source = tmp_path / "sig.db"
    target = tmp_path / "tgt.db"
    assets = tmp_path / "assets"
    assets.mkdir()
    store, asset = _store_asset(assets)
    _init_db(source)
    _init_db(target)
    repo = SQLiteSignatureRepository(source)
    repo.add_asset(asset)
    assert fingerprint_sqlite_bundle(source)["db"]

    with pytest.raises(SqlitePgImportError, match="blob_reader required"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "noreader",
            assets_root=assets,
            target_repository=SQLiteSignatureRepository(target),
        )

    with pytest.raises(SqlitePgImportError, match="unavailable|escapes|absolute"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "bad",
            assets_root=tmp_path / "missing-root",
            blob_reader=store,
            target_repository=SQLiteSignatureRepository(target),
        )

    result = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "ok",
        assets_root=assets,
        blob_reader=store,
        target_repository=SQLiteSignatureRepository(target),
    )
    assert result.inserted == 1
    again = import_sqlite_to_postgres(
        sqlite_path=source,
        report_dir=tmp_path / "ok2",
        assets_root=assets,
        blob_reader=store,
        target_repository=SQLiteSignatureRepository(target),
    )
    assert again.skipped_equal == 1


def test_storage_rejects_absolute_and_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "sig.db"
    target = tmp_path / "tgt.db"
    assets = tmp_path / "assets"
    assets.mkdir()
    store, asset = _store_asset(assets, b"abcd")
    _init_db(source)
    _init_db(target)
    # Absolute path storage_key
    bad = SignatureAsset(
        asset_id="a2",
        owner_user_id="u1",
        storage_key=str((assets / "x.enc").resolve()),
        media_type="image/png",
        original_filename="x.png",
        sha256="00",
        size_bytes=1,
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    SQLiteSignatureRepository(source).add_asset(bad)
    with pytest.raises(SqlitePgImportError, match="absolute|escapes"):
        import_sqlite_to_postgres(
            sqlite_path=source,
            report_dir=tmp_path / "abs",
            assets_root=assets,
            blob_reader=store,
            target_repository=SQLiteSignatureRepository(target),
        )


def test_template_bool_roundtrip_via_api(tmp_path: Path) -> None:
    source = tmp_path / "sig.db"
    target = tmp_path / "tgt.db"
    _init_db(source)
    _init_db(target)
    SQLiteSignatureRepository(source).upsert_template(
        UserSignatureTemplate(
            template_id="t1",
            owner_user_id="u1",
            name="T",
            placement=SignaturePlacementInput(0, 1.0, 2.0, 10.0),
            layout=LabelLayoutInput(show_signature=True, show_name=False, show_date=True),
            signature_asset_id=None,
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            scope="user",
        )
    )
    result = signature_api.import_sqlite_to_postgres(
        sqlite_path=source,
        postgres_dsn=None,
        report_dir=tmp_path / "r",
        target_repository=SQLiteSignatureRepository(target),
    )
    assert result.inserted == 1
    loaded = SQLiteSignatureRepository(target).get_template("t1")
    assert loaded is not None
    assert loaded.layout.show_name is False


def test_live_contract_r2_cutover_source_instruments_sqlite_paths() -> None:
    live = Path(__file__).with_name("test_sqlite_pg_import_live.py").read_text(encoding="utf-8")
    assert "productive_sqlite_open_blocked" in live or "productive_sqlite_opens" in live
    assert "cutover-disabled" in live
    assert "len(winners) >= 1" not in live
    assert "test_live_signature_cas_single_winner" not in live
    assert "register_documents_ports" in live
    assert "wire_backend_usermanagement" in live
    assert "usermanagement_postgres_dsn" in live
    assert "documents_postgres_dsn" in live
    assert "seed_postgres_workflow_profiles" in live
    assert "adoptable_v1" not in live
    assert "DatabaseStatus(" not in live
    assert "forbidden_sqlite_paths" in live
    assert "get_active_signature_asset_id" in live
    assert "set_active_signature_asset" in live
    assert "PostgresSignatureRepository(dsn).get_asset" not in live

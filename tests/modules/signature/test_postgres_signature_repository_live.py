"""Live PostgreSQL repository tests for AP-029 PG01-D signature."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
import pytest

from modules.signature import postgres_schema as signature_schema
from modules.signature.contracts import LabelLayoutInput, SignatureAsset, SignaturePlacementInput, UserSignatureTemplate
from modules.signature.postgres_connection import PostgresRepositoryError
from modules.signature.postgres_repository import PostgresSignatureRepository
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


@pytest.fixture
def signature_repository(live_postgres_env: LivePostgresEnv) -> PostgresSignatureRepository:
    signature_schema.provision_signature_schema(live_postgres_env.admin_dsn)
    signature_schema.migrate_signature_schema(live_postgres_env.migrator_dsn)
    repository = PostgresSignatureRepository(live_postgres_env.runtime_dsn)
    yield repository
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS signature CASCADE")


def _sample_asset(asset_id: str = "asset-pg-1") -> SignatureAsset:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return SignatureAsset(
        asset_id=asset_id,
        owner_user_id="user-1",
        storage_key="user-1/sample.png.enc",
        media_type="image/png",
        original_filename="sample.png",
        sha256="abc123",
        size_bytes=42,
        created_at=moment,
    )


def _sample_template(template_id: str = "tpl-pg-1", asset_id: str | None = "asset-pg-1") -> UserSignatureTemplate:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return UserSignatureTemplate(
        template_id=template_id,
        owner_user_id="user-1",
        name="Live template",
        placement=SignaturePlacementInput(page_index=0, x=12.0, y=34.0, target_width=80.0),
        layout=LabelLayoutInput(show_signature=True, show_name=True, show_date=False),
        signature_asset_id=asset_id,
        created_at=moment,
        scope="user",
    )


def test_postgres_signature_repository_metadata_roundtrip(signature_repository: PostgresSignatureRepository) -> None:
    asset = _sample_asset()
    signature_repository.add_asset(asset)
    loaded = signature_repository.get_asset("asset-pg-1")
    assert loaded == asset

    template = _sample_template()
    signature_repository.upsert_template(template)
    assert signature_repository.get_template("tpl-pg-1") == template
    assert signature_repository.list_templates("user-1") == [template]

    signature_repository.set_active_signature_asset("user-1", "asset-pg-1")
    assert signature_repository.get_active_signature_asset_id("user-1") == "asset-pg-1"

    signature_repository.clear_active_signature_asset("user-1")
    assert signature_repository.get_active_signature_asset_id("user-1") is None

    signature_repository.delete_template("tpl-pg-1")
    assert signature_repository.get_template("tpl-pg-1") is None


def test_postgres_signature_repository_global_templates(signature_repository: PostgresSignatureRepository) -> None:
    global_template = _sample_template("tpl-global", asset_id=None)
    global_template = UserSignatureTemplate(
        template_id=global_template.template_id,
        owner_user_id=global_template.owner_user_id,
        name=global_template.name,
        placement=global_template.placement,
        layout=global_template.layout,
        signature_asset_id=global_template.signature_asset_id,
        created_at=global_template.created_at,
        scope="global",
    )
    signature_repository.upsert_template(global_template)
    assert signature_repository.list_global_templates() == [global_template]


def test_postgres_signature_repository_rejects_migrator_login(
    live_postgres_env: LivePostgresEnv,
) -> None:
    signature_schema.provision_signature_schema(live_postgres_env.admin_dsn)
    signature_schema.migrate_signature_schema(live_postgres_env.migrator_dsn)
    repository = PostgresSignatureRepository(live_postgres_env.migrator_dsn)
    try:
        with pytest.raises(PostgresRepositoryError):
            repository.list_global_templates()
    finally:
        with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS signature CASCADE")

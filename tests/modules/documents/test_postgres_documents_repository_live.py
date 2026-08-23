"""Live PostgreSQL repository tests for AP-029 PG01-C documents (NOT RUN without Slot 2)."""
from __future__ import annotations

import pytest

from modules.documents.postgres_repository import PostgresDocumentsRepository

pytestmark = pytest.mark.postgres


def test_live_placeholder_skipped_without_slot2() -> None:
    pytest.skip("QMTOOL_PG_TEST_ADMIN_DSN is required for destructive PostgreSQL tests")

"""HttpDocumentsWorkflowApi profile-id derivation and fail-closed stubs."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from interfaces.clients.documents_http_ports import HttpDocumentsWorkflowApi
from modules.documents.api import DocumentsFeatureUnavailableError
from modules.documents.contracts import ControlClass


class HttpDocumentsWorkflowApiPortStubsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.api = HttpDocumentsWorkflowApi()

    def test_list_profile_ids_derives_from_unambiguous_definitions(self) -> None:
        rows = [
            {
                "profile_code": "long_release",
                "label": "Long",
                "control_class": "CONTROLLED",
                "is_active": True,
                "active_version": 1,
            },
            {
                "profile_code": "short_release",
                "label": "Short",
                "control_class": "CONTROLLED",
                "is_active": True,
                "active_version": 2,
            },
            {
                "profile_code": "info_only",
                "label": "Info",
                "control_class": "EXTERNAL",
                "is_active": True,
                "active_version": 1,
            },
        ]
        with patch.object(self.api, "list_workflow_profile_definitions", return_value=rows):
            ids = self.api.list_profile_ids_for_control_class(ControlClass.CONTROLLED)
        self.assertEqual(ids, ["long_release", "short_release"])

    def test_list_profile_ids_fail_closed_when_fields_missing(self) -> None:
        rows = [
            {
                "profile_code": "long_release",
                "control_class": "CONTROLLED",
                "is_active": True,
                # active_version missing
            }
        ]
        with patch.object(self.api, "list_workflow_profile_definitions", return_value=rows):
            with self.assertRaises(DocumentsFeatureUnavailableError):
                self.api.list_profile_ids_for_control_class(ControlClass.CONTROLLED)

    def test_ensure_source_pdf_for_signing_delegates_to_http_client(self) -> None:
        state = MagicMock(document_id="DOC", version=1, last_event_id="evt")
        expected_path = MagicMock()
        with patch.object(self.api, "_client") as client_factory:
            client = MagicMock()
            client_factory.return_value = client
            client.ensure_source_pdf_for_signing.return_value = expected_path
            result = self.api.ensure_source_pdf_for_signing(state)
        self.assertIs(result, expected_path)
        client.ensure_source_pdf_for_signing.assert_called_once_with(state)

    def test_create_new_version_after_archive_delegates_to_http_client(self) -> None:
        state = MagicMock(document_id="DOC", version=1, last_event_id="evt")
        expected = MagicMock()
        with patch.object(self.api, "_client") as client_factory:
            client = MagicMock()
            client_factory.return_value = client
            client.create_new_version_after_archive.return_value = expected
            result = self.api.create_new_version_after_archive(state, 2)
        self.assertIs(result, expected)
        client.create_new_version_after_archive.assert_called_once_with(state, 2)


if __name__ == "__main__":
    unittest.main()

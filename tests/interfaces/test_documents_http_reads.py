from __future__ import annotations

from unittest.mock import MagicMock, patch

from interfaces.clients.documents_http_ports import HttpDocumentsPoolApi


def test_http_pool_routes_all_new_reads_through_documents_client() -> None:
    client = MagicMock()
    client.get_header.return_value = object()
    client.list_tasks.return_value = [object()]
    client.list_review_actions.return_value = [object()]
    client.list_recent_documents.return_value = [object()]
    client.list_released_documents.return_value = [object()]
    client.get_capabilities.return_value = {"can_create_new_documents": True}
    pool = HttpDocumentsPoolApi()

    with patch(
        "interfaces.clients.documents_http_ports.DocumentsHttpClient.for_runtime",
        return_value=client,
    ):
        assert pool.get_header("DOC-1") is client.get_header.return_value
        assert pool.list_tasks_for_user("client-supplied", "Admin", scope="mine") == client.list_tasks.return_value
        assert pool.list_review_actions_for_user("client-supplied", "Admin") == client.list_review_actions.return_value
        assert pool.list_recent_documents_for_user("client-supplied", "Admin") == client.list_recent_documents.return_value
        assert pool.list_current_released_documents() == client.list_released_documents.return_value
        assert pool.get_capabilities() == client.get_capabilities.return_value

    client.list_tasks.assert_called_once_with(scope="mine")
    client.list_review_actions.assert_called_once_with()
    client.list_recent_documents.assert_called_once_with()


def test_http_read_routes_all_training_reads_through_documents_client() -> None:
    from unittest.mock import MagicMock, patch

    from interfaces.clients.documents_http_ports import HttpDocumentsReadApi

    client = MagicMock()
    read_api = HttpDocumentsReadApi()

    with patch(
        "interfaces.clients.documents_http_ports.DocumentsHttpClient.for_runtime",
        return_value=client,
    ):
        read_api.open_released_document_for_training("ignored", "DOC-1", 2)
        read_api.get_read_receipt("ignored", "DOC-1", 2)

    client.open_released_document.assert_called_once_with("DOC-1", 2)
    client.get_read_receipt.assert_called_once_with("DOC-1", 2)
